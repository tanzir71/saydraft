"""First-run model checks use public metadata and disposable payloads only."""

import copy
import threading
from types import SimpleNamespace

from PySide6 import QtCore, QtTest, QtWidgets
import pytest

from saydraft.asr.model_ids import DEFAULT_MODEL
from saydraft.config import default_config
from saydraft.models.setup import capability_recommendation, inspect_speech_package
from saydraft.models.tiers import effective_tier
from saydraft.ui.onboarding_models import OnboardingModelsPage


@pytest.mark.parametrize("ram,avx2,gpu,tier,model", [
    (4, True, False, "lite", "whisper-base"),
    (16, False, True, "lite", "whisper-base"),
    (8, True, False, "standard", DEFAULT_MODEL),
    (16, True, True, "pro", DEFAULT_MODEL),
    (None, True, True, "pending", DEFAULT_MODEL),
    (16, None, False, "pending", DEFAULT_MODEL),
    (True, True, True, "pending", DEFAULT_MODEL),
])
def test_capability_recommendation_is_provisional_and_does_not_qualify_a_tier(ram, avx2, gpu, tier, model):
    report = {"ram_bytes": ram * 1024**3 if type(ram) is int else ram,
        "cpu_features": {"avx2": avx2}, "vulkan": [{"name": "Public GPU"}] if gpu else []}
    before = copy.deepcopy(report)
    recommendation = capability_recommendation(report)
    assert recommendation == {"candidate_tier": tier, "speech_model": model, "provisional": True}
    assert report == before
    assert effective_tier(default_config(), report) == "pending"


def test_package_check_verifies_the_language_detector_as_well_as_primary_weights():
    calls = []

    def finder(model_id, *, check_hashes):
        calls.append((model_id, check_hashes))
        return None if model_id == "whisper-tiny-lid-int8" else "public fixture"

    result = inspect_speech_package(DEFAULT_MODEL, finder=finder)
    assert result["state"] == "missing" and "Whisper" in result["missing"][0]
    assert calls == [(DEFAULT_MODEL, True), ("whisper-tiny-lid-int8", True)]
    assert inspect_speech_package(DEFAULT_MODEL, finder=lambda *_a, **_k: "fixture") == {
        "state": "verified", "missing": []}
    assert inspect_speech_package("whisper-custom-fixture", finder=lambda *_a, **_k: pytest.fail("custom lookup")) == {
        "state": "custom", "missing": []}


def settle(page):
    for _ in range(300):
        QtWidgets.QApplication.processEvents()
        if page._future is None and not page._pending:
            return
        QtTest.QTest.qWait(5)
    raise AssertionError("Owned setup check did not settle")


@pytest.fixture
def subject():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    calls, downloads = [], []
    config = default_config()
    report = {"ram_bytes": 4 * 1024**3, "cpu_features": {"avx2": True}, "vulkan": []}

    def probe():
        calls.append("probe")
        return report

    page = OnboardingModelsPage(config, hardware_probe=probe,
        status_provider=lambda model: calls.append(("inspect", model)) or {"state": "missing", "missing": []},
        download_callback=lambda model, progress: downloads.append(model))
    try:
        yield SimpleNamespace(app=app, page=page, calls=calls, downloads=downloads, config=config, report=report)
    finally:
        page.close()
        app.processEvents()


def test_model_page_constructs_without_checks_and_requires_clicks_for_probe_recommendation_and_download(subject):
    s = subject
    before = copy.deepcopy(s.config)
    assert not s.calls and not s.downloads
    s.page.show()
    settle(s.page)
    assert s.calls == [("inspect", DEFAULT_MODEL)]
    s.page.hardware_button.click()
    settle(s.page)
    assert "Lite candidate" in s.page.recommendation.text()
    assert "not measured by this capability check" in s.page.recommendation.text()
    assert s.page.picker.model_id == DEFAULT_MODEL and not s.downloads
    s.page.use_button.click()
    settle(s.page)
    assert s.page.picker.model_id == "whisper-base" and not s.downloads
    assert s.config == before
    s.page.picker.start_download()
    for _ in range(100):
        s.app.processEvents()
        if s.page.picker.task is None:
            break
        QtTest.QTest.qWait(5)
    settle(s.page)
    assert s.downloads == ["base"]
    assert s.config == before


def test_model_readiness_is_not_inferred_from_a_download_callback_success(subject):
    page = subject.page
    page.show()
    settle(page)
    page.picker.start_download()
    from tests.test_model_picker import wait_finished
    wait_finished(page.picker)
    settle(page)
    assert page.readiness_state == "missing"
    assert "setup needed" in page.readiness.text()


def test_missing_hardware_information_is_not_presented_as_a_measured_tier(subject):
    subject.page.probe = lambda: {"errors": {"ram_bytes": "OSError"}}
    subject.page.show()
    settle(subject.page)
    subject.page.hardware_button.click()
    settle(subject.page)
    assert "pending" in subject.page.recommendation.text()
    assert not subject.page.use_button.isEnabled()


def test_stale_model_checks_are_ignored_and_only_the_latest_selection_is_queued(subject):
    started, release = threading.Event(), threading.Event()
    calls = []

    def inspect(model):
        calls.append(model)
        if len(calls) == 1:
            started.set()
            assert release.wait(3)
            return {"state": "verified", "missing": []}
        return {"state": "missing", "missing": ["Public missing model"]}

    page = subject.page
    page.inspect = inspect
    try:
        page.show()
        assert started.wait(1)
        timer = []
        QtCore.QTimer.singleShot(0, lambda: timer.append(True))
        page.picker.combo.setCurrentIndex(page.picker.combo.findData("whisper-small"))
        page.picker.combo.setCurrentIndex(page.picker.combo.findData("whisper-large-v3-turbo"))
        subject.app.processEvents()
        assert timer and len(page._pending) == 1
        release.set()
        settle(page)
        assert calls == [DEFAULT_MODEL, "whisper-large-v3-turbo"]
        assert page.readiness_state == "missing"
        assert "Public missing model" in page.readiness.text()
    finally:
        release.set()


def test_hiding_setup_invalidates_late_pc_results_and_allows_an_explicit_retry(subject):
    started, release = threading.Event(), threading.Event()
    page = subject.page

    def probe():
        started.set()
        assert release.wait(3)
        return {"ram_bytes": 16 * 1024**3, "cpu_features": {"avx2": True}, "vulkan": [{}]}

    page.probe = probe
    try:
        page.show()
        settle(page)
        page.hardware_button.click()
        assert started.wait(1)
        page.hide()
        release.set()
        settle(page)
        assert page._candidate is None and "cancelled" in page.recommendation.text()
        page.probe = lambda: subject.report
        page.show()
        settle(page)
        page.hardware_button.click()
        settle(page)
        assert page._candidate["candidate_tier"] == "lite"
    finally:
        release.set()


def test_closing_does_not_join_a_blocked_read_only_probe(subject):
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    page = subject.page

    def probe():
        started.set()
        try:
            assert release.wait(3)
        finally:
            finished.set()
        return subject.report

    page.probe = probe
    try:
        page.show()
        settle(page)
        page.hardware_button.click()
        assert started.wait(1)
        page.close()
        assert page._closed and not finished.is_set()
        release.set()
        assert finished.wait(1)
        subject.app.processEvents()
        assert page._candidate is None
    finally:
        release.set()


def test_recommendation_cannot_change_a_model_during_its_download(subject):
    from tests.test_model_picker import wait_finished

    started, release = threading.Event(), threading.Event()
    page = subject.page
    page.show()
    settle(page)
    page.hardware_button.click()
    settle(page)
    assert page._candidate["speech_model"] == "whisper-base"

    def download(*_args, **_kwargs):
        started.set()
        assert release.wait(3)

    page.picker.callback = download
    try:
        page.picker.start_download()
        assert started.wait(1)
        assert not page.use_button.isEnabled()
        page.use_recommendation()
        assert page.picker.model_id == DEFAULT_MODEL
        release.set()
        wait_finished(page.picker)
    finally:
        release.set()


def test_failed_checks_show_generic_status_and_allow_retry(subject):
    def fail(*_args):
        raise OSError("private fixture path")

    page = subject.page
    page.inspect = page.probe = fail
    page.show()
    settle(page)
    assert page.readiness_state == "failed" and "private" not in page.readiness.text()
    page.hardware_button.click()
    settle(page)
    assert page.hardware_button.isEnabled() and not page.use_button.isEnabled()
    assert "private" not in page.recommendation.text()
