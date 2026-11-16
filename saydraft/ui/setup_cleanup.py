"""Optional local cleanup setup, using the same explicit downloader as Settings."""

from PySide6 import QtCore, QtWidgets
from .cleanup_picker import CleanupPicker
from .kit import Card, Label, Toggle, SettingRow


def cleanup_files_present(config, model_id):
    from saydraft.paths import resolve_data_path
    from saydraft.model_download import find_installed_model
    from saydraft.models.downloader import installation_ready
    from saydraft.models.manifest import get_model
    from saydraft.models.runtime_ids import runtime_model_id

    if not config["llm"]["enabled"]:
        return True
    path = resolve_data_path(config["llm"]["model_path"])
    if not path.is_file() or path.suffix.lower() != ".gguf":
        return False
    if model_id and not installation_ready(
        get_model(model_id), path.parent, check_hashes=False
    ):
        return False
    runtime = runtime_model_id(config["llm"]["backend"])
    directory = find_installed_model(runtime)
    return directory is not None and installation_ready(
        get_model(runtime), directory, check_hashes=False
    )


class SetupCleanup(Card):
    changed = QtCore.Signal()

    def __init__(
        self, config, *, callback=None, runtime_callback=None, status_provider=None
    ):
        super().__init__(padding=20)
        self.body.setSpacing(12)
        # Expanding the optional downloader must increase the scroll content's
        # minimum height, rather than compressing its controls to zero height.
        self.body.setSizeConstraint(QtWidgets.QLayout.SetMinimumSize)
        policy = QtWidgets.QSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Minimum
        )
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)
        self.initial = dict(config["llm"])
        self.inspect = status_provider or cleanup_files_present
        self.body.addWidget(Label("Local AI cleanup · optional", "subheading"))
        self.body.addWidget(
            Label(
                "Rules cleanup works immediately. Add a local model for more substantial rewriting. Review the size and license before downloading.",
                "muted",
            )
        )
        self.enabled = Toggle("Enable local AI cleanup")
        self.enabled.setChecked(config["llm"]["enabled"])
        self.body.addWidget(SettingRow("Enable local AI cleanup", self.enabled))
        self.picker = CleanupPicker(
            config,
            callback=callback,
            runtime_callback=runtime_callback,
            apply_label="Finish setup",
        )
        self.picker.setProperty("bare", True)
        self.details = QtWidgets.QWidget(self)
        self.details.setProperty("bare", True)
        self.details.setSizePolicy(policy)
        details = QtWidgets.QVBoxLayout(self.details)
        details.setContentsMargins(0, 0, 0, 0)
        details.setSpacing(12)
        details.setSizeConstraint(QtWidgets.QLayout.SetMinimumSize)
        details.addWidget(self.picker)
        self.path = QtWidgets.QLineEdit(config["llm"]["model_path"])
        self.path.setAccessibleName("Existing local AI cleanup GGUF path")
        details.addWidget(self.path)
        self.body.addWidget(self.details)
        self.status = Label("", "caption")
        self.body.addWidget(self.status)
        self.picker.ready.connect(self._ready)
        self.picker.finished.connect(self.refresh)
        self.picker.combo.currentIndexChanged.connect(self._choice)
        self.picker.backend.currentIndexChanged.connect(self.refresh)
        self.enabled.toggled.connect(self.refresh)
        self.path.textChanged.connect(self.refresh)
        self.refresh()

    def apply_to(self, config):
        values = dict(
            enabled=self.enabled.isChecked(),
            model_path=self.path.text().strip(),
            backend=self.picker.backend.currentData(),
        )
        for key, value in values.items():
            if value != self.initial.get(key):
                config["llm"][key] = value

    def can_finish(self, config=None):
        if self.picker.task is not None:
            return False
        if config is None:
            config = {"llm": dict(self.initial)}
            config["llm"].update(
                enabled=self.enabled.isChecked(),
                model_path=self.path.text().strip(),
                backend=self.picker.backend.currentData(),
            )
        try:
            return bool(self.inspect(config, self.picker.combo.currentData()))
        except (OSError, ValueError):
            return False

    def refresh(self, *_args):
        self.details.setVisible(self.enabled.isChecked())
        if not self.enabled.isChecked() and self.picker.task is not None:
            self.picker.pause()
        self.path.setVisible(self.picker.combo.currentData() is None)
        self._complete = self.can_finish()
        self.status.setText(
            "Continue with rules cleanup; you can add AI later."
            if not self.enabled.isChecked()
            else "Selected local files are present. They are checked again before use."
            if self._complete
            else "Download or resume a cleanup model and processor files, or turn AI cleanup off to continue with rules."
        )
        self.details.layout().invalidate()
        self.body.invalidate()
        self.updateGeometry()
        parent = self.parentWidget()
        if parent is not None and parent.layout() is not None:
            layout = parent.layout()
            index = layout.indexOf(self)
            if isinstance(layout, QtWidgets.QBoxLayout) and index >= 0:
                # Qt retains this item's old height-for-width after expanding
                # the nested downloader. Renew only the layout item; the card,
                # its controls, transfers and signal owners stay untouched.
                layout.removeWidget(self)
                layout.insertWidget(index, self)
            layout.invalidate()
            parent.updateGeometry()
        self.changed.emit()

    def _choice(self, *_args):
        model_id = self.picker.combo.currentData()
        if model_id:
            from saydraft.model_download import (
                find_installed_model,
                default_models_dir,
                model_relative_dir,
            )
            from saydraft.models.manifest import get_model

            model = get_model(model_id)
            directory = find_installed_model(
                model_id
            ) or default_models_dir() / model_relative_dir(model)
            self.path.setText(
                str(
                    directory
                    / next(
                        f["path"] for f in model["files"] if f["path"].endswith(".gguf")
                    )
                )
            )
        self.refresh()

    def _ready(self, path, backend):
        self.path.setText(path)
        self.picker.backend.setCurrentIndex(self.picker.backend.findData(backend))
        self.refresh()

    def pause(self):
        self.picker.pause()
