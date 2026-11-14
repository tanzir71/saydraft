"""Auto or up to three language pins; choosing languages never downloads weights."""

from PySide6 import QtCore, QtWidgets

from saydraft.asr.languages import LANGUAGE_LABELS, WHISPER_LANGUAGES, normalize_pins
from saydraft.asr.router import ALL_LANGUAGES, choose_route


def language_choices():
    """Alphabetical display names shared by speech settings and text previews."""
    choices = []
    for code in WHISPER_LANGUAGES:
        locale = QtCore.QLocale({"jw": "jv"}.get(code, code))
        name = QtCore.QLocale.languageToString(locale.language())
        if locale.language() == QtCore.QLocale.C:
            name = code
        choices.append((LANGUAGE_LABELS.get(code, name), code))
    return tuple(sorted(choices))


class LanguagesPage(QtWidgets.QWidget):
    changed = QtCore.Signal()

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.routing = QtWidgets.QCheckBox("Choose the speech model automatically")
        self.routing.setChecked(config["stt"].get("routing_enabled", False))
        self.english_max = QtWidgets.QCheckBox("English max when English is the only pinned language")
        self.english_max.setChecked(config["stt"].get("english_max", False))
        self.combos = [QtWidgets.QComboBox() for _ in range(3)]
        self.combos[0].addItem("Auto", None)
        for combo in self.combos[1:]:
            combo.addItem("None", None)
        for name, code in language_choices():
            for combo in self.combos:
                combo.addItem(f"{name} ({code})", code)
        pins = config["stt"].get("pinned_languages", [])
        legacy = config["stt"].get("language", "auto")
        if not pins and legacy != "auto" and legacy in WHISPER_LANGUAGES:
            pins = [legacy]
        for combo, pin in zip(self.combos, pins):
            combo.setCurrentIndex(combo.findData(pin))
        self.note = QtWidgets.QLabel()
        self.note.setWordWrap(True)
        form = QtWidgets.QFormLayout(self)
        form.addRow(self.routing)
        for index, combo in enumerate(self.combos, 1):
            form.addRow(f"Language {index}", combo)
        form.addRow(self.english_max)
        form.addRow(self.note)
        for combo in self.combos:
            combo.currentIndexChanged.connect(self._changed)
        self.routing.toggled.connect(self._changed)
        self.english_max.toggled.connect(self._changed)
        self._update_note()

    def pins(self):
        if self.combos[0].currentData() is None:
            return ()
        return normalize_pins([combo.currentData() for combo in self.combos])

    def _update_note(self):
        auto = self.combos[0].currentData() is None
        for combo in self.combos[1:]:
            combo.setEnabled(not auto)
        route = choose_route(self.pins(), english_max=self.english_max.isChecked())
        self.english_max.setEnabled(self.routing.isChecked())
        if not self.routing.isChecked():
            self.note.setText("The model selected on the Models tab is used. Language pins supply a "
                              "single-language hint to Whisper when one language is selected. "
                              "Choose a compatible model on Models, or enable automatic model choice here. "
                              "Language selection starts no download.")
        elif route.model_id == ALL_LANGUAGES:
            self.note.setText("These languages use the optional shared All languages model. "
                              "Download it once on the Models tab; switching between supported languages "
                              "reuses the same model files. There are no separate language packs. "
                              "Language selection starts no download.")
        elif route.reason == "english_max":
            self.note.setText("English max uses Parakeet v2. Download it on the Models tab if needed.")
        elif route.reason == "pinned_supported":
            note = "These languages use Parakeet v3. Language selection starts no download."
            if 'pt' in self.pins():
                note += " Portuguese includes Brazilian Portuguese under the shared pt code; there is no separate Brazil model."
            self.note.setText(note)
        else:
            self.note.setText("Auto starts with Parakeet v3. Pin one to three languages to guide model choice. "
                              "Languages outside its set, including Thai, Chinese, Bengali and Arabic, "
                              "use the optional shared All languages model. Spanish, French, German and "
                              "Portuguese are included in Parakeet v3.")

    def _changed(self):
        self._update_note()
        self.changed.emit()

    def apply_to(self, config):
        pins = self.pins()
        config["stt"]["routing_enabled"] = self.routing.isChecked()
        config["stt"]["pinned_languages"] = list(pins)
        config["stt"]["language"] = pins[0] if len(pins) == 1 else "auto"
        config["stt"]["english_max"] = self.english_max.isChecked()
