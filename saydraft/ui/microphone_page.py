"""Explicit device discovery and a generation-scoped, level-only input test."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import math

from PySide6 import QtCore, QtGui, QtWidgets

from saydraft.audio.devices import InputSelection, list_inputs
from .progress import ThemedProgressBar


class MicrophonePage(QtWidgets.QWidget):
    devices_ready = QtCore.Signal(int, object)

    def __init__(self, config, *, start_callback=None, stop_callback=None, devices_provider=None,
                 apply_label="Save", show_title=True, parent=None):
        super().__init__(parent)
        self.apply_label = apply_label
        self.start_callback, self.stop_callback = start_callback, stop_callback
        self.provider = devices_provider or list_inputs
        self._selection = InputSelection.from_config(config)
        self._devices, self._pool, self._future = None, None, None
        self._scan_generation, self._test_generation = 0, 0
        self._closed = self._stopping = False
        layout = QtWidgets.QVBoxLayout(self)
        def paragraph(text, *, display=False):
            label = QtWidgets.QLabel(text)
            label.setTextFormat(QtCore.Qt.PlainText)
            label.setWordWrap(True)
            policy = label.sizePolicy()
            policy.setHorizontalPolicy(QtWidgets.QSizePolicy.Ignored)
            label.setSizePolicy(policy)
            if display:
                label.setProperty("role", "display")
            layout.addWidget(label)
            return label
        if show_title:
            paragraph("Microphone", display=True)
        paragraph(f"Choose an input for dictation. {apply_label} applies it to future recordings; Test input uses the selected choice now.")
        self.device_combo = QtWidgets.QComboBox()
        self.device_combo.setAccessibleName("Dictation microphone")
        self.device_combo.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)
        layout.addWidget(self.device_combo)
        actions = QtWidgets.QHBoxLayout()
        self.refresh_button = QtWidgets.QPushButton("Refresh inputs")
        self.test_button = QtWidgets.QPushButton("Test input")
        actions.addWidget(self.refresh_button)
        actions.addWidget(self.test_button)
        layout.addLayout(actions)
        self.level_bar = ThemedProgressBar()
        self.level_bar.setRange(0,100)
        self.level_bar.setValue(0)
        self.level_bar.setTextVisible(False)
        self.level_bar.setAccessibleName("Microphone input level")
        layout.addWidget(self.level_bar)
        paragraph("Say ‘testing one two three’ and watch the meter. The test stops after 10 seconds. Audio is neither saved nor transcribed, and no sound is played.")
        self.status = paragraph("")
        paragraph("If access is blocked, allow desktop apps in Windows microphone privacy settings.")
        self.sound_button = QtWidgets.QPushButton("Open Windows sound settings")
        self.privacy_button = QtWidgets.QPushButton("Open microphone privacy settings")
        self.sound_button.clicked.connect(lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl("ms-settings:sound")))
        self.privacy_button.clicked.connect(lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl("ms-settings:privacy-microphone")))
        layout.addWidget(self.sound_button)
        layout.addWidget(self.privacy_button)
        layout.addStretch()
        self.device_combo.currentIndexChanged.connect(self._selection_changed)
        self.refresh_button.clicked.connect(self.refresh_devices)
        self.test_button.clicked.connect(self.toggle_test)
        self.devices_ready.connect(self._accept_devices, QtCore.Qt.QueuedConnection)
        self.destroyed.connect(self._shutdown)
        QtWidgets.QApplication.instance().aboutToQuit.connect(self._shutdown)
        self.set_selection(self._selection)

    def set_selection(self, selection):
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        self.device_combo.addItem("Default Windows input", InputSelection())
        counts = Counter(device.selection.key for device in self._devices or ())
        seen = set()
        for device in self._devices or ():
            if device.selection.key not in seen:
                self.device_combo.addItem(device.label + (" (multiple inputs)" if counts[device.selection.key]>1 else ""), device.selection)
                seen.add(device.selection.key)
        index = next((i for i in range(self.device_combo.count()) if self.device_combo.itemData(i).key==selection.key), -1)
        if index < 0:
            self.device_combo.addItem(f"{selection.name} · {selection.hostapi} (" +
                ("refresh to check" if self._devices is None else "unavailable") + ")", selection)
            index = self.device_combo.count()-1
        self.device_combo.setCurrentIndex(index)
        self.device_combo.blockSignals(False)
        self._selection = self.device_combo.currentData()
        self._update_actions()

    @property
    def selection(self):
        return self._selection

    def _selection_changed(self):
        self.stop_test()
        self._selection = self.device_combo.currentData()
        self.level_bar.setValue(0)
        if not self._test_generation:
            self.status.setText(f"Input choice changed. {self.apply_label} to use it for future dictation.")
        self._update_actions()

    def _available(self):
        return not self.selection.name or self._devices is None or sum(
            device.selection.key==self.selection.key for device in self._devices)==1

    def _update_actions(self):
        self.test_button.setText("Stop test" if self._test_generation else "Test input")
        self.test_button.setEnabled(not self._closed and not self._stopping and
            bool(self.stop_callback if self._test_generation else self.start_callback and self._available()))
        self.refresh_button.setEnabled(not self._closed and not self._test_generation and
            (self._future is None or self._future.done()))

    def refresh_devices(self):
        if self._closed or self._test_generation or self._future is not None and not self._future.done():
            return False
        self._scan_generation += 1
        generation = self._scan_generation
        if self._pool is None:
            self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="Saydraft-inputs")
        self.status.setText("Checking available inputs…")
        def run():
            try:
                result = tuple(self.provider())
            except Exception:
                result = None
            if not self._closed:
                try:
                    self.devices_ready.emit(generation,result)
                except RuntimeError:
                    pass
        self._future = self._pool.submit(run)
        self.refresh_button.setEnabled(False)
        return True

    @QtCore.Slot(int,object)
    def _accept_devices(self, generation, devices):
        if self._closed or generation!=self._scan_generation:
            return
        self._future = None
        if devices is None:
            self.status.setText("Could not list inputs. Check Windows sound settings and try again.")
        else:
            self._devices = devices
            self.set_selection(self.selection)
            self.status.setText("Inputs refreshed." if self._available() else
                "The selected input is unavailable or ambiguous. Choose another input or Default Windows input.")
        self._update_actions()

    def toggle_test(self):
        if self._test_generation:
            return self.stop_test()
        if self._closed or self.start_callback is None or not self._available():
            return False
        try:
            generation = self.start_callback(self.selection)
        except Exception:
            generation = 0
        if type(generation) is not int or generation<=0:
            self.status.setText("Finish the current dictation or retry before testing the microphone.")
            return False
        self._test_generation, self._stopping = generation, False
        self.level_bar.setValue(0)
        self.status.setText("Opening the selected input…")
        self._update_actions()
        return True

    def stop_test(self):
        if not self._test_generation or self._stopping or self.stop_callback is None:
            return False
        self._stopping = True
        self._update_actions()
        self.status.setText("Stopping input test…")
        try:
            stopped = bool(self.stop_callback(self._test_generation))
        except Exception:
            stopped = False
        if not stopped:
            self._stopping = False
            self.status.setText("Could not stop the input test yet. Try Stop test again.")
            self._update_actions()
        return stopped

    @QtCore.Slot(int,float)
    def accept_level(self, generation, level):
        if not self._closed and generation==self._test_generation and not self._stopping and math.isfinite(level):
            self.level_bar.setValue(min(100,max(0,round(level*400))))

    @QtCore.Slot(int,str)
    def accept_status(self, generation, state):
        if self._closed or generation!=self._test_generation:
            return
        if state in ("stopped","failed"):
            self._test_generation, self._stopping = 0, False
            self.level_bar.setValue(0)
            self.status.setText("Input test finished." if state=="stopped" else
                "Could not use this input. Check the device, other audio apps and microphone privacy settings.")
        elif state=="listening" and not self._stopping:
            self.status.setText("Listening for input level only…")
        self._update_actions()

    def hideEvent(self,event):
        self.stop_test()
        super().hideEvent(event)

    def closeEvent(self,event):
        self._shutdown()
        super().closeEvent(event)

    @QtCore.Slot()
    def _shutdown(self):
        if not self._closed:
            self.stop_test()
            self._closed = True
            if self._pool is not None:
                self._pool.shutdown(wait=False,cancel_futures=True)
