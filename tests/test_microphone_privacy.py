import ctypes
import os
import threading
import time
from types import SimpleNamespace

import pytest

from saydraft.audio.privacy import STATES, _windows_status, check_microphone_privacy
from saydraft.config import default_config
from saydraft.ui.microphone_page import MicrophonePage
from tests.test_onboarding_window import qt_modules


@pytest.mark.parametrize('value,expected', [*STATES.items(), (-1, 'unknown'), (99, 'unknown'),
    (True, 'unknown'), (None, 'unknown'), ('allowed', 'unknown')])
def test_privacy_status_is_explicit_and_unknown_is_not_permission(value, expected):
    assert check_microphone_privacy(query=lambda: value) == expected


def test_unsupported_or_failed_privacy_query_has_no_exception_details(monkeypatch):
    monkeypatch.setattr('saydraft.audio.privacy.os.name', 'other')
    assert check_microphone_privacy() == 'unknown'
    assert check_microphone_privacy(query=lambda: 4) == 'allowed'
    for error in (OSError('private detail'), ValueError('private detail'), TypeError('private detail')):
        def failed():
            raise error
        assert check_microphone_privacy(query=failed) == 'unknown'


class WinRT:
    """Real ABI-shaped public interfaces; every request slot is forbidden."""
    def __init__(self, *, initialized=0, fail='', status=4):
        self.calls, self.keep, self.initialized, self.fail, self.status = [], [], initialized, fail, status
        self.next_handle = 100
        for name in ('RoInitialize', 'RoUninitialize', 'WindowsCreateString', 'WindowsDeleteString', 'RoGetActivationFactory'):
            setattr(self, name, self.function(name))
        self.capability = self.interface('capability', 10)
        self.factory = self.interface('factory', 9)

    def function(self, name):
        def call(*args):
            self.calls.append(name)
            if self.fail == name:
                return -2147467259
            if name == 'RoInitialize':
                return self.initialized
            if name == 'WindowsCreateString':
                self.next_handle += 1
                ctypes.cast(args[2], ctypes.POINTER(ctypes.c_void_p))[0] = self.next_handle
            if name == 'RoGetActivationFactory':
                ctypes.cast(args[2], ctypes.POINTER(ctypes.c_void_p))[0] = ctypes.cast(self.factory, ctypes.c_void_p)
            return 0
        return call

    def interface(self, name, size):
        pointer = ctypes.c_void_p
        callback = getattr(ctypes, 'WINFUNCTYPE', ctypes.CFUNCTYPE)

        def forbidden(_self):
            self.calls.append('FORBIDDEN')
            return -2147467259

        forbidden_callback = callback(ctypes.c_long, pointer)(forbidden)
        self.keep.append(forbidden_callback)
        table = (pointer * size)(*[ctypes.cast(forbidden_callback, pointer)] * size)

        def release(_self):
            self.calls.append(name + '.Release')
            return 0
        release_callback = callback(ctypes.c_ulong, pointer)(release)
        self.keep.append(release_callback)
        table[2] = ctypes.cast(release_callback, pointer)
        if name == 'factory':
            def create(_self, _name, result):
                self.calls.append('Create')
                if self.fail == 'Create':
                    return -2147467259
                result[0] = ctypes.cast(self.capability, pointer)
                return 0
            method = callback(ctypes.c_long, pointer, pointer, ctypes.POINTER(pointer))(create)
            index = 8
        else:
            def check(_self, result):
                self.calls.append('CheckAccess')
                if self.fail == 'CheckAccess':
                    return -2147467259
                result[0] = self.status
                return 0
            method = callback(ctypes.c_long, pointer, ctypes.POINTER(ctypes.c_int32))(check)
            index = 9
        self.keep.extend((method, table))
        table[index] = ctypes.cast(method, pointer)
        instance = (ctypes.POINTER(pointer) * 1)(ctypes.cast(table, ctypes.POINTER(pointer)))
        self.keep.append(instance)
        return instance


@pytest.mark.skipif(os.name != 'nt', reason='Windows WinRT ABI')
@pytest.mark.parametrize('initialized,uninitializes', [(0, 1), (1, 1), (-2147417850, 0)])
def test_in_process_query_never_requests_access_and_balances_native_lifetimes(initialized, uninitializes):
    api = WinRT(initialized=initialized, status=2)
    assert _windows_status(api=api) == 2
    assert 'FORBIDDEN' not in api.calls
    assert api.calls.count('CheckAccess') == 1
    assert api.calls.count('WindowsDeleteString') == 2
    assert api.calls.count('RoUninitialize') == uninitializes
    assert api.calls.index('capability.Release') < api.calls.index('factory.Release')


@pytest.mark.skipif(os.name != 'nt', reason='Windows WinRT ABI')
@pytest.mark.parametrize('fail,releases,strings', [('RoInitialize', 0, 0), ('WindowsCreateString', 0, 0),
    ('RoGetActivationFactory', 0, 2), ('Create', 1, 2), ('CheckAccess', 2, 2)])
def test_failed_native_query_releases_only_owned_resources(fail, releases, strings):
    api = WinRT(fail=fail)
    assert check_microphone_privacy(query=lambda: _windows_status(api=api)) == 'unknown'
    assert sum(call.endswith('.Release') for call in api.calls) == releases
    assert api.calls.count('WindowsDeleteString') == strings
    assert api.calls.count('RoUninitialize') == (fail != 'RoInitialize')
    assert 'FORBIDDEN' not in api.calls


def wait_for(predicate, *, timeout=3):
    qt = qt_modules()
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        qt.QtWidgets.QApplication.processEvents()
        if predicate():
            return
        time.sleep(.002)
    raise AssertionError('Owned privacy query did not settle')


@pytest.fixture
def subject():
    qt = qt_modules()
    entered, release, calls = threading.Event(), threading.Event(), []

    def forbidden(*args, **kwargs):
        raise AssertionError('Privacy checks cannot enumerate/open devices or use the clipboard')

    def provider():
        calls.append(threading.get_ident())
        entered.set()
        assert release.wait(3)
        return 'allowed'

    page = MicrophonePage(default_config(), privacy_provider=provider, devices_provider=forbidden,
        start_callback=forbidden, stop_callback=forbidden)
    page.show()
    try:
        yield SimpleNamespace(page=page, qt=qt, entered=entered, release=release, calls=calls)
    finally:
        release.set()
        page.close()
        if page._privacy_pool is not None:
            page._privacy_pool.shutdown(wait=True)
        qt.QtWidgets.QApplication.processEvents()


def test_check_is_explicit_responsive_and_queued_back_to_the_gui(subject):
    s = subject
    assert not s.calls
    assert s.page.check_privacy() and s.entered.wait(1)
    assert not s.page.check_privacy() and not s.page.privacy_check_button.isEnabled()
    assert 'Checking' in s.page.privacy_status.text()
    assert s.page._test_generation == 0 and s.page._devices is None
    assert s.page.sound_button.isEnabled() and s.page.privacy_button.isEnabled()
    s.release.set()
    wait_for(lambda: s.page._privacy_future is None)
    assert s.calls == [s.calls[0]] and s.calls[0] != threading.get_ident()
    assert 'access is allowed' in s.page.privacy_status.text()
    assert s.page.privacy_check_button.isEnabled()


@pytest.mark.parametrize('dismiss', ['hide', 'close'])
@pytest.mark.parametrize('queued', [False, True])
def test_dismissal_revokes_running_and_already_queued_results(subject, dismiss, queued):
    s = subject
    assert s.page.check_privacy() and s.entered.wait(1)
    future = s.page._privacy_future
    if queued:
        s.release.set()
        s.page._privacy_future.result(timeout=2)
    getattr(s.page, dismiss)()
    s.release.set()
    future.result(timeout=2)
    s.qt.QtWidgets.QApplication.processEvents()
    assert 'access is allowed' not in s.page.privacy_status.text()
    if dismiss == 'hide':
        s.page.show()
        assert s.page.privacy_check_button.isEnabled()
        assert s.page.check_privacy()
        wait_for(lambda: s.page._privacy_future is None)
        assert 'access is allowed' in s.page.privacy_status.text()
    else:
        assert not s.page.check_privacy()


@pytest.mark.parametrize('state,phrase', [('denied_by_user', 'access is off'),
    ('denied_by_system', 'administrator'), ('not_declared', 'has not declared'),
    ('prompt_required', 'not been granted'), ('unknown', 'Could not determine'), ([], 'Could not determine')])
def test_permission_guidance_is_separate_from_device_and_test_status(subject, state, phrase):
    s = subject
    s.page.privacy_provider = lambda: state
    s.page.status.setText('Input choice changed.')
    assert s.page.check_privacy()
    wait_for(lambda: s.page._privacy_future is None)
    assert phrase in s.page.privacy_status.text()
    assert s.page.status.text() == 'Input choice changed.'


def test_provider_and_queue_failures_are_generic_and_explicit_retry_works(subject):
    s = subject

    def failed():
        raise OSError('private provider detail')
    s.page.privacy_provider = failed
    assert s.page.check_privacy()
    wait_for(lambda: s.page._privacy_future is None)
    assert 'Could not determine' in s.page.privacy_status.text()
    s.page._privacy_pool.shutdown(wait=True)
    assert not s.page.check_privacy()
    assert s.page._privacy_pool is None and s.page.privacy_check_button.isEnabled()
    s.page.privacy_provider = lambda: 'allowed'
    assert s.page.check_privacy()
    wait_for(lambda: s.page._privacy_future is None)
    assert 'access is allowed' in s.page.privacy_status.text()


def test_executor_creation_failure_stays_unknown_and_can_retry(subject, monkeypatch):
    import saydraft.ui.microphone_page as module
    pool_type = module.ThreadPoolExecutor

    def failed(**kwargs):
        raise OSError('private queue detail')
    monkeypatch.setattr(module, 'ThreadPoolExecutor', failed)
    assert not subject.page.check_privacy()
    assert 'Could not determine' in subject.page.privacy_status.text()
    assert subject.page.privacy_check_button.isEnabled()
    monkeypatch.setattr(module, 'ThreadPoolExecutor', pool_type)
    subject.release.set()
    assert subject.page.check_privacy()
    wait_for(lambda: subject.page._privacy_future is None)
    assert 'access is allowed' in subject.page.privacy_status.text()


@pytest.mark.parametrize('container', ['setup', 'settings'])
def test_shared_product_controls_run_only_after_click_and_do_not_save_preferences(tmp_path, monkeypatch, container):
    from tests.test_onboarding_window import fixture_wizard, write_config
    from tests.test_settings_window import FakeAutoStartManager
    from saydraft.ui.settings_page import SettingsPage

    qt_modules()
    path = write_config(tmp_path)
    original = path.read_bytes()
    calls = []
    monkeypatch.setattr('saydraft.ui.microphone_page.check_microphone_privacy',
        lambda: calls.append(threading.get_ident()) or 'denied_by_user')
    if container == 'setup':
        window = fixture_wizard(config_path=path)
        window.show()
        window.next()
    else:
        window = SettingsPage(config_path=path, snippets_path=tmp_path / 'snippets.txt',
            autostart_manager=FakeAutoStartManager())
        window.tabs.setCurrentIndex(next(i for i in range(window.tabs.count()) if window.tabs.tabText(i) == 'Microphone'))
        window.show()
    page = window.microphone_page
    try:
        assert not calls
        page.privacy_check_button.click()
        wait_for(lambda: page._privacy_future is None)
        assert len(calls) == 1 and calls[0] != threading.get_ident()
        assert 'access is off' in page.privacy_status.text()
        assert path.read_bytes() == original
    finally:
        window.close()
        page.close()


@pytest.mark.integration
@pytest.mark.offline
@pytest.mark.skipif(os.name != 'nt', reason='Windows capability metadata only')
def test_native_current_process_check_reads_capability_without_audio_or_network(monkeypatch):
    import sounddevice
    from saydraft.privacy.netguard import NetworkGuard

    def forbidden(*args, **kwargs):
        raise AssertionError('Only current-process capability metadata is permitted')
    for name in ('InputStream', 'query_devices', 'query_hostapis'):
        monkeypatch.setattr(sounddevice, name, forbidden)
    NetworkGuard.install()
    assert _windows_status() in STATES
