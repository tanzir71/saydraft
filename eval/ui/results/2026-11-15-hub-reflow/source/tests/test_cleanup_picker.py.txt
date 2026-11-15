"""Review choices first; install explicitly; activate only when Settings is applied."""

import copy
import threading
import time
from pathlib import Path

import pytest

from saydraft.config import default_config, load_config
from saydraft.models.cleanup import cleanup_bundle, transfer_bytes
from saydraft.models.downloader import DownloadPaused
from saydraft.ui.cleanup_picker import CleanupPicker
from tests.test_settings_window import make_window, qt_modules


def drain(widget):
    app = qt_modules().QtWidgets.QApplication.instance()
    stop = time.monotonic() + 5
    while widget.task is not None and time.monotonic() < stop:
        app.processEvents()
        time.sleep(.001)
    assert widget.task is None


def choose_model(picker):
    picker.combo.setCurrentIndex(picker.combo.findData("qwen35-2b-q4-k-m"))
    picker.backend.setCurrentIndex(picker.backend.findData("vulkan"))


def test_pro_recommendation_is_prefilled_without_transfer_or_config_change():
    qt_modules()
    config = default_config()
    before = copy.deepcopy(config)
    calls = []
    picker = CleanupPicker(config, callback=lambda *args: calls.append(args),
        report={"assessment": {"tier": "pro"}, "vulkan": [{"name": "GPU"}]})
    assert picker.combo.currentData() == "qwen35-2b-q4-k-m"
    assert picker.combo.findData("qwen35-4b-q4-k-m") == -1  # Command-only, not a cleanup promotion.
    assert picker.backend.currentData() == "vulkan" and not calls and config == before
    package = cleanup_bundle(picker.combo.currentData(), "vulkan")
    size = sum(transfer_bytes(model) for model in package) / 1e6
    assert f"{size:.1f} MB" in picker.license_label.text()
    assert "Apache-2.0" in picker.license_label.text() and "LLVM OpenMP" in picker.license_label.text()
    assert "Apply Settings" in picker.recommendation.text()


@pytest.mark.parametrize("tier", ["lite", "pending"])
def test_unmeasured_or_lite_does_not_preselect_model_and_custom_preferences_survive(tier):
    qt_modules()
    config = default_config()
    picker = CleanupPicker(config, report={"assessment": {"tier": tier}})
    assert picker.combo.currentData() is None
    config["llm"].update(enabled=True, model_path="private/custom.gguf", backend="cpu")
    preserved = CleanupPicker(config, report={"assessment": {"tier": "pro"}, "vulkan": [{}]})
    assert preserved.combo.currentData() is None and preserved.backend.currentData() == "cpu"
    preserved.refresh_recommendation({"assessment": {"tier": "standard"}})
    assert preserved.combo.currentData() is None and "Standard" in preserved.recommendation.text()


def test_explicit_download_returns_captured_choice_and_stays_separate_from_enable_and_apply(tmp_path):
    window, config_path, _ = make_window(tmp_path)
    picker = window.cleanup_picker
    calls = []
    output = tmp_path / "verified.gguf"
    output.write_bytes(b"test fixture")
    started, release = threading.Event(), threading.Event()
    def download(model, backend, progress, *, pause_event):
        calls.append((model, backend, pause_event))
        started.set()
        assert release.wait(3)
        progress(100)
        return output
    picker.callback = download
    choose_model(picker)
    old_path = window.llm_path_edit.text()
    picker.start_download()
    assert started.wait(3)
    assert not picker.combo.isEnabled() and not picker.backend.isEnabled()
    assert window.llm_path_edit.text() == old_path
    picker.start_download()  # No second concurrent transfer.
    release.set()
    drain(picker)
    assert len(calls) == 1 and calls[0][:2] == ("qwen35-2b-q4-k-m", "vulkan")
    assert window.llm_path_edit.text() == str(output) and not window.llm_enabled_checkbox.isChecked()
    assert load_config(config_path=config_path)["llm"]["model_path"] == old_path
    assert window.apply_changes()
    applied = load_config(config_path=config_path)["llm"]
    assert applied["model_path"] == str(output) and applied["backend"] == "vulkan" and not applied["enabled"]
    window.llm_enabled_checkbox.setChecked(True)
    assert window.apply_changes() and load_config(config_path=config_path)["llm"]["enabled"]
    window.close()


def test_failure_keeps_existing_path_and_retry_uses_same_explicit_choice(tmp_path):
    window, _, _ = make_window(tmp_path, overrides={"llm": {"model_path": "original.gguf"}})
    picker = window.cleanup_picker
    output = tmp_path / "ready.gguf"
    output.write_bytes(b"fixture")
    calls = []
    def download(*args, **kwargs):
        calls.append(args[:2])
        if len(calls) == 1:
            raise OSError("interrupted")
        return output
    picker.callback = download
    choose_model(picker)
    picker.start_download()
    drain(picker)
    assert window.llm_path_edit.text() == "original.gguf" and "retry" in picker.status.text()
    assert picker.download_button.isEnabled()
    picker.start_download()
    drain(picker)
    assert calls == [("qwen35-2b-q4-k-m", "vulkan")] * 2
    assert window.llm_path_edit.text() == str(output)
    window.close()


def test_closing_settings_pauses_worker_and_preserves_old_config(tmp_path):
    window, config_path, _ = make_window(tmp_path)
    picker = window.cleanup_picker
    started = threading.Event()
    def wait_for_pause(model, backend, progress, *, pause_event):
        started.set()
        assert pause_event.wait(3)
        raise DownloadPaused("Paused; verified files are kept")
    picker.callback = wait_for_pause
    choose_model(picker)
    picker.start_download()
    assert started.wait(3)
    before = Path(config_path).read_bytes()
    window.close()
    drain(picker)
    assert Path(config_path).read_bytes() == before and "Paused" in picker.status.text()


def test_custom_model_can_install_only_runtime_without_changing_path_or_downloading_weights(tmp_path):
    window, _, _ = make_window(tmp_path, overrides={"llm": {"model_path": "owner.gguf", "backend": "vulkan"}})
    picker = window.cleanup_picker
    calls = []
    picker.callback = lambda *args, **kwargs: pytest.fail("Custom path must not download catalog weights")
    picker.runtime_callback = lambda backend, progress, **kwargs: calls.append(backend) or tmp_path
    picker.start_download()
    drain(picker)
    assert calls == ["vulkan"] and window.llm_path_edit.text() == "owner.gguf"
    assert "Processor files verified" in picker.status.text() and not window.llm_enabled_checkbox.isChecked()
    window.close()


@pytest.mark.parametrize("result", ["", "missing.gguf"])
def test_unusable_setup_result_cannot_replace_existing_path(tmp_path, result):
    window, _, _ = make_window(tmp_path, overrides={"llm": {"model_path": "kept.gguf"}})
    picker = window.cleanup_picker
    choose_model(picker)
    picker.callback = lambda *args, **kwargs: result
    picker.start_download()
    drain(picker)
    assert window.llm_path_edit.text() == "kept.gguf" and "retry" in picker.status.text()
    window.close()
