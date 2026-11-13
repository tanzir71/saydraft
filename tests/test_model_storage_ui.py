import time
import threading

import pytest

from saydraft.config import default_config
from saydraft.models.storage import RemovalResult
from saydraft.ui.model_storage import ModelStorage
from tests.test_model_storage import make_subject, snapshot
from tests.test_settings_window import qt_modules


@pytest.fixture
def subject(tmp_path):
    return make_subject(tmp_path)


def settle(page):
    qt = qt_modules()
    deadline = time.monotonic() + 5
    while page.task is not None and time.monotonic() < deadline:
        qt.QtWidgets.QApplication.processEvents()
        time.sleep(0.005)
    assert page.task is None


def test_inventory_is_background_and_removal_requires_concrete_confirmation(subject):
    qt_modules()
    calls, confirmed = [], []
    page = ModelStorage(config_provider=default_config, inventory_provider=lambda: snapshot(subject),
                        remove_callback=lambda entry: calls.append(entry) or RemovalResult(2, entry.size))
    page.refresh()
    settle(page)
    assert "logical file size" in page.summary.text() and "other or cached files" in page.summary.text()
    assert str(subject[2]) in page.details.text() and page.remove_button.isEnabled()
    page.confirm = lambda entry: confirmed.append(entry) or False
    page.request_remove()
    assert len(confirmed) == 1 and not calls and page.task is None
    page.confirm = lambda entry: confirmed.append(entry) or True
    page.request_remove()
    settle(page)
    assert calls == [confirmed[-1]] and calls[0].path == subject[2]
    assert "Removed 2 files" in page.status.text()
    assert (subject[2] / "weights.gguf").exists()  # UI fixture callback does not delete.
    page.close()


def test_saved_gguf_path_blocks_removal_until_another_model_is_saved(subject):
    qt_modules()
    config = default_config()
    config["llm"]["model_path"] = str(subject[2] / "weights.gguf")
    page = ModelStorage(config_provider=lambda: config, inventory_provider=lambda: snapshot(subject),
                        remove_callback=lambda entry: (_ for _ in ()).throw(AssertionError("must not remove")))
    page.refresh()
    settle(page)
    assert not page.remove_button.isEnabled() and "Configured or loaded" in page.details.text()
    page.confirm = lambda entry: (_ for _ in ()).throw(AssertionError("must not prompt"))
    page.request_remove()
    assert "Configured or loaded" in page.status.text()
    config["llm"]["model_path"] = "elsewhere.gguf"
    page.selection_changed()
    assert page.remove_button.isEnabled()
    page.close()


def test_confirmation_dialog_names_version_folder_size_and_defaults_to_cancel(subject):
    qt = qt_modules()
    page = ModelStorage(config_provider=default_config)
    entry = snapshot(subject).models[0]
    observed = []
    def dismiss():
        dialog = qt.QtWidgets.QApplication.activeModalWidget()
        cancel = dialog.buttons.button(qt.QtWidgets.QDialogButtonBox.Cancel)
        observed.append((dialog.details.toPlainText(), cancel.text(), cancel.isDefault(),
                         dialog.details.isReadOnly(), dialog.details.horizontalScrollBar().maximum()))
        dialog.reject()
    qt.QtCore.QTimer.singleShot(0, dismiss)
    assert not page._confirm(entry)
    text, default_button, is_default, read_only, overflow = observed[0]
    assert entry.label in text and entry.revision in text and str(entry.path) in text
    assert "Recognized files" in text and default_button == "Cancel"
    assert is_default and read_only and overflow == 0
    page.close()


def test_inventory_failure_recovers_without_enabling_remove():
    qt_modules()
    page = ModelStorage(config_provider=default_config,
                        inventory_provider=lambda: (_ for _ in ()).throw(OSError("fixture unavailable")))
    page.refresh()
    settle(page)
    assert "fixture unavailable" in page.status.text()
    assert page.refresh_button.isEnabled() and not page.remove_button.isEnabled()
    page.close()


def test_refresh_during_background_scan_is_replayed_after_completion(subject):
    qt_modules()
    entered, release = threading.Event(), threading.Event()
    calls = []
    def inspect():
        calls.append(True)
        if len(calls) == 1:
            entered.set()
            assert release.wait(5)
        return snapshot(subject)
    page = ModelStorage(config_provider=default_config, inventory_provider=inspect)
    page.refresh()
    try:
        assert entered.wait(2)
        page.refresh()
        page.refresh()
        assert len(calls) == 1
    finally:
        release.set()
        settle(page)
        page.close()
    assert len(calls) == 2


def test_confirmed_ui_removal_runs_through_idle_worker_and_real_fixture_storage(subject, monkeypatch):
    from saydraft.models import storage
    from tests.test_session_worker import make_worker
    qt_modules()
    monkeypatch.setattr(storage, "storage_roots", lambda: [subject[0]])
    worker, *_ = make_worker()
    page = ModelStorage(config_provider=lambda: worker.services.config,
                        inventory_provider=lambda: snapshot(subject), remove_callback=worker.remove_stored_model)
    try:
        page.refresh()
        settle(page)
        page.confirm = lambda entry: False
        page.request_remove()
        assert (subject[2] / "weights.gguf").exists()
        page.confirm = lambda entry: True
        page.request_remove()
        settle(page)
        assert not subject[2].exists() and not worker.busy
        assert page.snapshot.models == () and "Removed 2 files" in page.status.text()
    finally:
        page.close()
        worker.shutdown()
