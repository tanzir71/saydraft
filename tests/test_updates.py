import json
import socket
from urllib.error import HTTPError

import pytest

from saydraft.config import default_config, sanitize_config
from saydraft.privacy.netguard import NetworkBlockedError, NetworkGuard, _check
from saydraft.updates import (LATEST_RELEASE, MAX_RESPONSE_BYTES, RELEASE_PAGE, UpdateController,
                              UpdateResult, _NoRedirects, check_updates)

pytestmark = pytest.mark.offline


def release(version='0.2.0', **changes):
    return {'draft': False, 'prerelease': False, 'published_at': '2026-11-14T00:00:00Z',
            'tag_name': 'v' + version, 'html_url': RELEASE_PAGE + 'v' + version, **changes}


class Response:
    def __init__(self, payload):
        self.payload, self.closed = payload, False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.closed = True

    def read(self, limit):
        return self.payload[:limit]


class Transport:
    def __init__(self, payload=None):
        self.response = Response(json.dumps(release()).encode() if payload is None else payload)
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        _check('api.github.com', dns=True)
        with pytest.raises(NetworkBlockedError):
            _check('downloads.example', dns=True)
        return self.response


@pytest.mark.parametrize('enabled', [False, None, 1, 'true', 'false'])
def test_disabled_or_unapproved_check_does_not_create_a_transport_or_resolve_dns(monkeypatch, enabled):
    def forbidden(*_args, **_kwargs):
        pytest.fail('Disabled update check touched the network')

    monkeypatch.setattr('saydraft.updates.build_opener', forbidden)
    monkeypatch.setattr(socket, 'getaddrinfo', forbidden)
    assert check_updates(enabled=enabled) == UpdateResult()


def test_opt_in_only_fetches_fixed_public_metadata_and_scope_is_retired_afterward():
    transport = Transport()
    NetworkGuard.install()
    try:
        result = check_updates(enabled=True, current_version='0.1.0', opener=transport)
        assert result == UpdateResult('available', '0.2.0') and result.url == RELEASE_PAGE + 'v0.2.0'
        assert len(transport.calls) == 1 and transport.response.closed
        request, timeout = transport.calls[0]
        assert request.full_url == LATEST_RELEASE and request.get_method() == 'GET' and timeout == 5
        assert not request.has_header('Authorization') and request.data is None
        for host in ['api.github.com', 'github.com', 'downloads.example']:
            with pytest.raises(NetworkBlockedError):
                socket.getaddrinfo(host, 443)
    finally:
        NetworkGuard.uninstall()


@pytest.mark.parametrize('version', ['0.1.0', '0.0.9'])
def test_equal_or_older_release_never_offers_a_downgrade(version):
    assert check_updates(enabled=True, current_version='0.1.0',
                         opener=Transport(json.dumps(release(version)).encode())) == UpdateResult('current')


def test_versions_are_compared_numerically_instead_of_lexically():
    assert check_updates(enabled=True, current_version='0.9.9',
                         opener=Transport(json.dumps(release('0.10.0')).encode())).state == 'available'


@pytest.mark.parametrize('change,state', [({'draft': True}, 'no_release'), ({'prerelease': True}, 'no_release'),
    ({'published_at': None}, 'unavailable'), ({'draft': None}, 'unavailable'), ({'prerelease': None}, 'unavailable')])
def test_drafts_prereleases_and_incomplete_publication_metadata_are_not_updates(change, state):
    result = check_updates(enabled=True, opener=Transport(json.dumps(release(**change)).encode()))
    assert result == UpdateResult(state) and result.url is None


@pytest.mark.parametrize('payload', [b'not JSON', b'[]', b'{}', b'\xff', b'x' * (MAX_RESPONSE_BYTES + 1),
    json.dumps(release(html_url='https://evil.example/installer.exe')).encode(),
    json.dumps(release(tag_name='v0.2.0-beta.1')).encode(),
    json.dumps(release(tag_name='v0.2.0/../../escape')).encode()])
def test_invalid_or_oversized_metadata_cannot_supply_a_release_link(payload):
    result = check_updates(enabled=True, opener=Transport(payload))
    assert result.state in ('unavailable', 'no_release') and result.url is None


@pytest.mark.parametrize('code,state', [(404, 'no_release'), (403, 'unavailable'), (429, 'unavailable'), (500, 'unavailable')])
def test_http_errors_are_visible_without_interrupting_dictation(code, state):
    class ErrorTransport:
        def open(self, *_args, **_kwargs):
            raise HTTPError(LATEST_RELEASE, code, 'fixture', {}, None)

    assert check_updates(enabled=True, opener=ErrorTransport()) == UpdateResult(state)


def test_redirect_is_rejected_before_any_second_request():
    with pytest.raises(OSError):
        _NoRedirects().redirect_request(None, None, 302, '', {}, 'https://evil.example/')


def test_default_transport_disables_ambient_proxies_and_redirects(monkeypatch):
    from urllib.request import ProxyHandler

    transport = Transport()
    handlers = []

    def builder(*values):
        handlers.extend(values)
        return transport

    monkeypatch.setattr('saydraft.updates.build_opener', builder)
    assert check_updates(enabled=True).state == 'available'
    assert any(isinstance(value, ProxyHandler) and value.proxies == {} for value in handlers)
    assert any(isinstance(value, _NoRedirects) for value in handlers)


def test_cancel_before_response_body_is_consumed_closes_it_without_publishing_a_release():
    cancelled = [False]
    transport = Transport()
    original = transport.open

    def opening(*args, **kwargs):
        response = original(*args, **kwargs)
        cancelled[0] = True
        return response

    transport.open = opening
    assert check_updates(enabled=True, opener=transport, cancelled=lambda: cancelled[0]) == UpdateResult()
    assert transport.response.closed


def test_existing_and_malformed_profiles_keep_the_default_off():
    assert default_config()['updates'] == {'enabled': False}
    for value in [None, {}, {'enabled': 1}, {'enabled': 'true'}]:
        assert sanitize_config({'updates': value})['updates'] == {'enabled': False}


class PendingThread:
    calls = []

    def __init__(self, *, target, name, daemon):
        assert name == 'Saydraft-update-check' and daemon is True
        self.target = target
        self.calls.append(self)

    def start(self):
        pass


def controller(checker=None):
    PendingThread.calls = []
    events = []
    service = UpdateController(events.append, checker=checker or (lambda **_: UpdateResult('available', '0.2.0')),
                               thread_factory=PendingThread)
    return service, events


def test_opt_in_starts_one_background_check_and_repeated_save_does_not_repeat_it():
    service, events = controller()
    assert not service.check() and not PendingThread.calls
    assert service.configure(True) and len(PendingThread.calls) == 1
    assert not service.configure(True) and not service.check()
    PendingThread.calls[0].target()
    assert service.result.state == 'available' and service.is_current(events[-1])


def test_opt_out_retires_queued_success_and_old_threads_cannot_restore_it():
    service, events = controller()
    service.configure(True)
    PendingThread.calls[0].target()
    available = events[-1]
    service.configure(False)
    assert service.result.state == 'disabled' and not service.is_current(available)
    assert not service.check()


def test_disable_before_queued_request_starts_cancels_its_network_admission():
    requests = []

    def checker(**options):
        requests.append(options['cancelled']())
        return UpdateResult('available', '0.2.0')

    service, _ = controller(checker)
    service.configure(True)
    service.configure(False)
    PendingThread.calls[0].target()
    assert requests == [True] and service.result.state == 'disabled'


def test_reenable_waits_for_old_request_then_uses_one_new_generation():
    service, events = controller()
    service.configure(True)
    service.configure(False)
    service.configure(True)
    assert len(PendingThread.calls) == 1
    PendingThread.calls[0].target()
    assert len(PendingThread.calls) == 2 and service.result.state == 'checking'
    PendingThread.calls[1].target()
    assert service.result.state == 'available' and service.is_current(events[-1])


def test_shutdown_suppresses_result_without_joining_a_request():
    service, events = controller()
    service.configure(True)
    service.close()
    count = len(events)
    PendingThread.calls[0].target()
    assert len(events) == count and not service.enabled and not service.configure(True)
