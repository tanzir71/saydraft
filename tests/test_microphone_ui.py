import threading
import time

import pytest

from saydraft.audio.devices import InputDevice, InputSelection
from saydraft.config import default_config,load_config
from saydraft.ui.microphone_page import MicrophonePage
from tests.test_history_window import qt_modules
from tests.test_settings_window import FakeAutoStartManager,write_config
from tests.test_microphone import Meter


def settle(page,timeout=3):
    app=qt_modules().QtWidgets.QApplication.instance()
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        app.processEvents()
        if page._future is None:
            return
        time.sleep(.003)
    raise AssertionError("Owned input discovery did not finish")


@pytest.fixture
def subject():
    qt=qt_modules()
    starts,stops=[],[]
    devices=(InputDevice(7,InputSelection("Public USB mic","Windows WASAPI")),
        InputDevice(2,InputSelection("Public headset","MME")))
    page=MicrophonePage(default_config(),devices_provider=lambda:devices,
        start_callback=lambda selection:starts.append(selection) or len(starts),
        stop_callback=lambda generation:stops.append(generation) or True)
    try:
        yield page,qt,devices,starts,stops
    finally:
        page.close()


def test_page_never_discovers_or_opens_input_on_construction_and_uses_only_explicit_test(subject):
    page,_,devices,starts,stops=subject
    assert page._future is None and page._devices is None and not starts and not stops
    assert page.selection==InputSelection()
    assert page.refresh_devices()
    settle(page)
    page.device_combo.setCurrentIndex(1)
    assert page.selection==devices[0].selection and not starts
    assert page.toggle_test() and starts==[devices[0].selection]
    assert page.test_button.text()=="Stop test" and not page.refresh_button.isEnabled()


def test_saved_missing_device_is_preserved_and_never_silently_replaced_by_default(subject):
    page,_,_,starts,_=subject
    missing=InputSelection("Missing owner mic","MME")
    page.set_selection(missing)
    page.refresh_devices()
    settle(page)
    assert page.selection==missing and "unavailable" in page.device_combo.currentText()
    assert not page.test_button.isEnabled() and not page.toggle_test() and not starts
    page.device_combo.setCurrentIndex(0)
    assert page.selection==InputSelection() and page.test_button.isEnabled()


def test_input_change_stops_old_test_and_late_levels_cannot_revive_it(subject):
    page,_,devices,_,stops=subject
    page.refresh_devices()
    settle(page)
    assert page.toggle_test()
    page.accept_status(1,"listening")
    page.accept_level(1,.125)
    assert page.level_bar.value()==50
    page.device_combo.setCurrentIndex(1)
    assert stops==[1] and not page.test_button.isEnabled()
    page.accept_level(1,.9)
    assert page.level_bar.value()==0
    page.accept_status(1,"stopped")
    assert page.toggle_test()
    page.accept_level(1,.9)
    page.accept_status(1,"failed")
    assert page._test_generation==2 and page.selection==devices[0].selection
    assert page.level_bar.value()==0


def test_hiding_the_page_requests_stop_without_waiting_for_device_closure(subject):
    page,qt,_,_,stops=subject
    page.show()
    qt.QtWidgets.QApplication.processEvents()
    page.toggle_test()
    page.hide()
    assert stops==[1] and page._stopping
    page.accept_status(1,"stopped")
    assert page._test_generation==0


def test_slow_discovery_keeps_gui_responsive_and_close_discards_late_result(subject):
    page,qt,devices,_,_=subject
    entered,release=threading.Event(),threading.Event()
    def blocked():
        entered.set()
        assert release.wait(3)
        return devices
    page.provider=blocked
    try:
        assert page.refresh_devices() and entered.wait(1)
        ticks=[]
        qt.QtCore.QTimer.singleShot(0,lambda:ticks.append(True))
        qt.QtWidgets.QApplication.processEvents()
        assert ticks and not page.refresh_button.isEnabled()
        page.close()
        release.set()
        page._future.result(timeout=2)
        qt.QtWidgets.QApplication.processEvents()
        assert page._devices is None
    finally:
        release.set()


def test_failed_discovery_and_stop_do_not_expose_provider_details_and_allow_retry(subject):
    page,_,_,_,_=subject
    page.provider=lambda:(_ for _ in ()).throw(RuntimeError("private driver details"))
    page.refresh_devices()
    settle(page)
    assert "private" not in page.status.text() and page.refresh_button.isEnabled()
    assert page.toggle_test()
    page.stop_callback=lambda generation:False
    assert not page.stop_test() and page.test_button.isEnabled()
    assert "Try Stop" in page.status.text()
    page.accept_status(1,"failed")


def test_device_preference_round_trips_through_shared_settings_save(tmp_path):
    from saydraft.ui.settings_page import SettingsPage
    qt_modules()
    config=write_config(tmp_path)
    stops=[]
    page=SettingsPage(config_path=config,snippets_path=tmp_path/"snippets.txt",autostart_manager=FakeAutoStartManager(),
        microphone_start_callback=lambda selection:9,microphone_stop_callback=lambda generation:stops.append(generation) or True)
    try:
        chosen=InputSelection("Public USB mic","Windows WASAPI")
        page.microphone_page.set_selection(chosen)
        assert page.microphone_page.toggle_test()
        assert page.apply_changes()
        assert stops==[9]
        assert InputSelection.from_config(load_config(config_path=config))==chosen
    finally:
        page.close()


def test_real_worker_controller_and_queued_qt_meter_signals_compose_without_capture(subject):
    from saydraft.app import WorkerController,create_worker_signals
    from tests.test_session_worker import make_worker
    page,qt,_,_,_=subject
    signals=create_worker_signals(qt.QtCore)
    controller=WorkerController(signals)
    worker,_,executor,events,_,_=make_worker(queued=True)
    controller.core=worker
    worker.emit_callback=controller._emit
    meters=[]
    worker.microphone_test.factory=lambda selection,**kwargs:meters.append(Meter(selection,**kwargs)) or meters[-1]
    signals.microphone_test_level.connect(page.accept_level,qt.QtCore.Qt.QueuedConnection)
    signals.microphone_test_status.connect(page.accept_status,qt.QtCore.Qt.QueuedConnection)
    page.start_callback=controller.start_microphone_test
    page.stop_callback=controller.stop_microphone_test
    try:
        assert page.toggle_test()
        executor.drain()
        emitter=threading.Thread(target=lambda:meters[0].kwargs["on_level"](.2))
        emitter.start()
        emitter.join(timeout=1)
        qt.QtWidgets.QApplication.processEvents()
        assert page.level_bar.value()==80 and "Listening" in page.status.text()
        assert not events and worker.services.recorder.started==0
        assert page.stop_test()
        executor.drain()
        qt.QtWidgets.QApplication.processEvents()
        assert meters[0].stopped and page._test_generation==0 and not worker.busy
    finally:
        worker.shutdown()
        executor.drain()


def test_leaving_the_actual_hub_page_and_closing_the_hub_request_input_stop(tmp_path):
    from saydraft.ui.hub import HubWindow
    from tests.test_history_window import build_history,FakeClipboard,settle_history
    qt=qt_modules()
    starts,stops=[],[]
    hub=HubWindow(settings_options=dict(config_path=write_config(tmp_path),snippets_path=tmp_path/"snippets.txt",
        autostart_manager=FakeAutoStartManager(),microphone_start_callback=lambda selection:starts.append(selection) or len(starts),
        microphone_stop_callback=lambda generation:stops.append(generation) or True),
        history_options=dict(store=build_history(tmp_path),clipboard=FakeClipboard()))
    page=hub.settings_page.microphone_page
    try:
        hub.show_page("Settings",tab="Microphone")
        hub.show()
        settle_history(hub.history_page)
        assert page.toggle_test()
        hub.show_page("Home")
        qt.QtWidgets.QApplication.processEvents()
        assert stops==[1]
        page.accept_status(1,"stopped")
        hub.show_page("Settings",tab="Microphone")
        assert page.toggle_test()
        hub.close()
        assert stops==[1,2]
        page.accept_status(2,"stopped")
    finally:
        page.close()
        hub.history_page.close()
        hub.close()
