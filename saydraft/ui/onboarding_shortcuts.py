"""Staged shortcut setup with explicit, focused, generation-scoped learning."""

from concurrent.futures import ThreadPoolExecutor
import re
import threading

from PySide6 import QtCore, QtWidgets

from saydraft.hotkeys.chords import Chord
from saydraft.hotkeys.recording import validate_hotkeys
from saydraft.hotkeys.wispr import shortcut_warning, wispr_running

_PRESET = {"speech": "ctrl+win", "hands_free": "ctrl+win+space", "paste_last": "shift+alt+z"}
_NAMES = {"speech": "Hold to dictate", "speech_alternative": "Alternate dictation",
          "speech_mouse": "Mouse dictation", "hands_free": "Hands-free",
          "paste_last": "Paste last", "save": "History capture", "cancel": "Cancel"}


class OnboardingShortcutsPage(QtWidgets.QWizardPage):
    conflict_checked = QtCore.Signal(int, object)

    def __init__(self, config, *, start_callback=None, cancel_callback=None, conflict_detector=None):
        super().__init__()
        self.setTitle("Shortcut")
        self.original = dict(config["hotkeys"])
        self.start_callback, self.cancel_callback = start_callback, cancel_callback
        self.detector = conflict_detector or wispr_running
        self._preset_mode = False
        self._generation = 0
        self._starting = False
        self._last_complete = None
        self._stopping = False
        self._permit = threading.Event()
        self._closed = False
        self._watched_window = None
        self._pool = self._probe_future = None
        self._probe_generation = 0
        self._probe_job = 0
        self._wispr = None
        self._have_check = False
        body = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(body)

        def paragraph(text, name):
            label = QtWidgets.QLabel(text)
            label.setTextFormat(QtCore.Qt.PlainText)
            label.setWordWrap(True)
            label.setAccessibleName(name)
            policy = label.sizePolicy()
            policy.setHorizontalPolicy(QtWidgets.QSizePolicy.Ignored)
            label.setSizePolicy(policy)
            layout.addWidget(label)
            return label

        paragraph("Choose the shortcut you will hold to dictate.",
                  "Shortcut learning instructions")
        form = QtWidgets.QFormLayout()
        form.setRowWrapPolicy(QtWidgets.QFormLayout.WrapAllRows)
        self.primary = QtWidgets.QLineEdit(str(self.original.get("speech", "")))
        self.primary.setMaxLength(128)
        self.primary.setAccessibleName("Hold-to-dictate shortcut")
        form.addRow("Hold to dictate", self.primary)
        layout.addLayout(form)
        self.learn_button = QtWidgets.QPushButton("Learn shortcut")
        self.learn_button.setAccessibleName("Learn dictation shortcut")
        self.learn_button.installEventFilter(self)
        layout.addWidget(self.learn_button)
        self.learn_status = paragraph("Learn listens for up to ten seconds while setup stays focused. "
                                      "Press and release your keys; Esc cancels.",
                                      "Shortcut learning status")
        self.validation = paragraph("", "Shortcut validation")
        self.preset_label = paragraph("", "Shortcut preset")
        self.preset_button = QtWidgets.QPushButton("Use Wispr-compatible preset")
        layout.addWidget(self.preset_button)
        self.summary = paragraph("", "Configured shortcuts")
        self.conflict_button = QtWidgets.QPushButton("Check other app conflicts")
        layout.addWidget(self.conflict_button)
        self.other_warning = paragraph("Other apps may use the same shortcuts. Check can identify "
                                       "a possible Wispr Flow default clash; custom bindings in other apps are unknown.",
                                       "Other app shortcut advisory")
        layout.addStretch(1)
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.scroll.setWidget(body)
        QtWidgets.QVBoxLayout(self).addWidget(self.scroll)
        self.primary.textChanged.connect(self._refresh)
        self.preset_button.clicked.connect(self.use_preset)
        self.learn_button.clicked.connect(self.start_learning)
        self.conflict_button.clicked.connect(self.check_other_apps)
        self.conflict_checked.connect(self._accept_check, QtCore.Qt.QueuedConnection)
        self.destroyed.connect(self._shutdown)
        QtWidgets.QApplication.instance().aboutToQuit.connect(self._shutdown)
        self._refresh()

    @property
    def learning(self):
        return bool(self._generation or self._starting)

    def draft_hotkeys(self):
        draft = dict(self.original)
        if self._preset_mode:
            draft.update(_PRESET)
        draft["speech"] = self.primary.text().strip()
        try:
            primary = Chord.parse(draft["speech"])
            for name in ("speech_alternative", "speech_mouse"):
                try:
                    if Chord.parse(draft.get(name, "")) == primary:
                        draft[name] = ""  # The same gesture now belongs to the primary action.
                except ValueError:
                    pass
        except ValueError:
            pass
        return draft

    def errors(self, hotkeys=None):
        hotkeys = self.draft_hotkeys() if hotkeys is None else hotkeys
        try:
            Chord.parse(hotkeys.get("speech", ""))
        except ValueError:
            return ["Enter a valid hold-to-dictate shortcut, such as Ctrl+Win or F9."]
        return validate_hotkeys(hotkeys)

    def merge_changes(self, latest):
        draft = self.draft_hotkeys()
        merged = dict(latest)
        merged.update({name: value for name, value in draft.items() if value != self.original.get(name)})
        errors = self.errors(merged)
        if errors:
            raise ValueError("Shortcut settings changed or conflict. Review the Shortcut step before finishing.")
        return merged

    def isComplete(self):
        return not self.learning and not self.errors()

    def _refresh(self):
        draft = self.draft_hotkeys()
        compatible = all(draft.get(name) == value for name, value in _PRESET.items())
        self.preset_label.setText("Wispr-compatible preset selected" if compatible else "Custom shortcuts preserved")
        errors = self.errors(draft)
        error = "\n".join(errors)
        for name, label in _NAMES.items():
            error = re.sub(r"\b" + name + r"\b", label, error)
        duplicate = [label for name, label in _NAMES.items()
                     if name in ("speech_alternative", "speech_mouse") and self.original.get(name) and not draft.get(name)]
        self.validation.setText(error or ("The identical " + ", ".join(duplicate) +
            " shortcut will be disabled; this gesture is now Hold to dictate." if duplicate else "Shortcut is valid."))
        self.summary.setText("\n".join(f"{label}: {draft.get(name) or 'Disabled'}" for name, label in _NAMES.items()))
        self.primary.setEnabled(not self.learning)
        self.preset_button.setEnabled(not self.learning)
        self.learn_button.setEnabled(not self._closed and not self._stopping and
            callable(self.start_callback) and callable(self.cancel_callback))
        self.learn_button.setText("Cancel learning" if self.learning else "Learn shortcut")
        if self._have_check and self._probe_future is None:
            self._show_other_warning()
        complete = self.isComplete()
        if complete != self._last_complete:
            self._last_complete = complete
            self.completeChanged.emit()

    def use_preset(self):
        if not self.learning:
            self._preset_mode = True
            self.primary.setText(_PRESET["speech"])
            self._refresh()

    def start_learning(self):
        if self.learning:
            self.cancel_learning()
            return False
        if self._closed or not callable(self.start_callback) or not callable(self.cancel_callback):
            return False
        # QWizard can briefly hide/re-layout a page when completeness changes.
        # Make navigation incomplete before granting the focused native lease.
        self._starting = True
        self._refresh()
        self.learn_button.setFocus(QtCore.Qt.OtherFocusReason)
        if not self.isVisible() or not self.window().isActiveWindow() or not self.learn_button.hasFocus():
            self._starting = False
            self._refresh()
            self.learn_status.setText("Keep setup focused and choose Learn shortcut again.")
            return False
        self._permit = threading.Event()
        self._permit.set()
        try:
            generation = self.start_callback(int(self.window().winId()), self._permit.is_set)
        except Exception:
            generation = 0
        self._starting = False
        if type(generation) is not int or generation <= 0:
            self._permit.clear()
            self._refresh()
            self.learn_status.setText("Shortcut learning is unavailable while the app is busy. Try again when it is idle.")
            return False
        self._generation = generation
        self._stopping = not self._permit.is_set()
        if self._stopping:
            self.cancel_callback(generation)
        self.learn_status.setText("Preparing shortcut learning… Release any keys already held.")
        self._refresh()
        self.scroll.ensureWidgetVisible(self.learn_status, 0, 8)
        return True

    @QtCore.Slot(int, str, str)
    def accept_status(self, generation, state, chord):
        if self._closed or not self._generation or generation != self._generation:
            return
        if state == "cleanup_failed":
            self._permit.clear()
            self._stopping = True
            self.learn_status.setText("Could not confirm shortcut learning stopped. Cancel setup and restart Saydraft before trying again.")
            self._refresh()
            self.scroll.ensureWidgetVisible(self.learn_status, 0, 8)
            return
        if state in ("preparing", "capturing"):
            if self._permit.is_set() and not self._stopping:
                self.learn_status.setText("Press your shortcut, then release every key. Esc cancels." if state == "capturing"
                                          else "Preparing shortcut learning… Release any keys already held.")
                self.scroll.ensureWidgetVisible(self.learn_status, 0, 8)
            return
        if state not in ("captured", "cancelled", "expired", "invalid", "failed"):
            return
        allowed = (self._permit.is_set() and self.isVisible() and self.window().isActiveWindow()
                   and self.learn_button.hasFocus() and not self._stopping)
        self._permit.clear()
        self._generation = 0
        self._stopping = False
        if state == "captured":
            try:
                Chord.parse(chord)
            except ValueError:
                state = "invalid"
            else:
                if allowed:
                    self.primary.setText(chord)
                else:
                    state = "cancelled"
        self.learn_status.setText({"captured": "Shortcut captured. Review it before continuing.",
            "cancelled": "Learning cancelled. Your shortcut is unchanged.",
            "expired": "Learning timed out after ten seconds. Choose Learn shortcut to try again.",
            "invalid": "Use modifiers with at most one other key or side mouse button, or modifiers alone.",
            "failed": "Could not complete shortcut learning. Try again or enter the shortcut manually."}[state])
        self._refresh()

    def cancel_learning(self):
        self._permit.clear()
        if self._generation and not self._stopping:
            self._stopping = True
            self.learn_status.setText("Stopping shortcut learning…")
            try:
                self.cancel_callback(self._generation)
            except Exception:
                pass
            self._refresh()

    def eventFilter(self, watched, event):
        if ((watched is self.learn_button and event.type() == QtCore.QEvent.FocusOut)
                or (watched is self._watched_window and event.type() in
                    (QtCore.QEvent.WindowDeactivate, QtCore.QEvent.WindowBlocked, QtCore.QEvent.Hide, QtCore.QEvent.Close))):
            self.cancel_learning()
        return super().eventFilter(watched, event)

    def showEvent(self, event):
        window = self.window()
        if window is not self._watched_window:
            if self._watched_window is not None:
                self._watched_window.removeEventFilter(self)
            self._watched_window = window
            window.installEventFilter(self)
        super().showEvent(event)

    def hideEvent(self, event):
        self.cancel_learning()
        self._probe_generation += 1
        if self._probe_future is not None:
            self.other_warning.setText("Other-app check cancelled. Choose Check other app conflicts to try again.")
        super().hideEvent(event)

    def check_other_apps(self):
        if self._closed or self._probe_future is not None:
            return False
        self._probe_generation += 1
        generation = self._probe_generation
        self._probe_job = generation
        self.conflict_button.setEnabled(False)
        self.other_warning.setText("Checking for a possible Wispr Flow shortcut clash…")
        if self._pool is None:
            self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="Saydraft-shortcut-check")

        def check():
            try:
                result = self.detector()
            except Exception:
                result = None
            try:
                self.conflict_checked.emit(generation, result)
            except RuntimeError:
                pass

        self._probe_future = self._pool.submit(check)
        return True

    @QtCore.Slot(int, object)
    def _accept_check(self, generation, result):
        if not self._closed and generation == self._probe_job:
            self._probe_future = None
            self.conflict_button.setEnabled(True)
        if self._closed or generation != self._probe_generation:
            return
        self._wispr = result
        self._have_check = True
        self.conflict_button.setEnabled(True)
        self._show_other_warning()
        self.scroll.ensureWidgetVisible(self.other_warning, 0, 8)

    def _show_other_warning(self):
        self.other_warning.setText(shortcut_warning(self.draft_hotkeys(), detector=lambda: self._wispr) or
            ("Could not check other apps. Review any shared shortcuts before dictating." if self._wispr is None else
             "Other apps' custom shortcuts are unknown. Wispr Flow's default has no detected clash with this choice."))

    @QtCore.Slot()
    def _shutdown(self):
        if not self._closed:
            self.cancel_learning()
            self._closed = True
            self._probe_generation += 1
            if self._pool is not None:
                self._pool.shutdown(wait=False, cancel_futures=True)

    def closeEvent(self, event):
        self._shutdown()
        super().closeEvent(event)
