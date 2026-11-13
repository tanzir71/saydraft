"""Opt-in public release metadata checks; application updates are installed by hand."""

from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from . import __version__
from .privacy.netguard import NetworkGuard

LATEST_RELEASE = 'https://api.github.com/repos/tanzir71/saydraft/releases/latest'
RELEASE_PAGE = 'https://github.com/tanzir71/saydraft/releases/tag/'
MAX_RESPONSE_BYTES = 262_144
SOCKET_TIMEOUT = 5


def version_parts(value):
    if not isinstance(value, str) or not re.fullmatch(r'(0|[1-9][0-9]{0,5})\.(0|[1-9][0-9]{0,5})\.(0|[1-9][0-9]{0,5})', value):
        raise ValueError('Expected a stable three-part version')
    return tuple(int(part) for part in value.split('.'))


@dataclass(frozen=True)
class UpdateResult:
    state: str = 'disabled'
    version: str | None = None

    def __post_init__(self):
        if self.state not in ('disabled', 'checking', 'available', 'current', 'no_release', 'unavailable'):
            raise ValueError('Unknown update state')
        if self.state == 'available':
            version_parts(self.version)
        elif self.version is not None:
            raise ValueError('Only an available release has a version')

    @property
    def url(self):
        return RELEASE_PAGE + 'v' + self.version if self.state == 'available' else None


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        raise URLError('Release metadata redirects are not allowed')


def check_updates(*, enabled=False, current_version=__version__, opener=None, cancelled=lambda: False):
    # Do not construct a transport, resolve DNS, or enter an exception to the
    # offline policy unless the saved opt-in is an actual boolean True.
    if enabled is not True or cancelled():
        return UpdateResult()
    try:
        installed = version_parts(current_version)
        request = Request(LATEST_RELEASE, headers={
            'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2026-03-10',
            'User-Agent': f'Saydraft/{current_version} update-check',
        }, method='GET')
        transport = opener or build_opener(ProxyHandler({}), _NoRedirects())
        with NetworkGuard.allow_update_check():
            if cancelled():
                return UpdateResult()
            with transport.open(request, timeout=SOCKET_TIMEOUT) as response:
                if cancelled():
                    return UpdateResult()
                content = response.read(MAX_RESPONSE_BYTES + 1)
        if cancelled():
            return UpdateResult()
        if len(content) > MAX_RESPONSE_BYTES:
            raise ValueError('Release response exceeds limit')
        payload = json.loads(content.decode('utf-8'))
        if not isinstance(payload, dict):
            raise ValueError('Release response is not an object')
        if payload.get('draft') is not False or payload.get('prerelease') is not False or not payload.get('published_at'):
            return UpdateResult('no_release')
        tag = payload.get('tag_name')
        if not isinstance(tag, str) or not tag.startswith('v'):
            raise ValueError('Release tag is invalid')
        version = tag[1:]
        latest = version_parts(version)
        if payload.get('html_url') != RELEASE_PAGE + tag:
            raise ValueError('Release page does not belong to this repository')
        return UpdateResult('available', version) if latest > installed else UpdateResult('current')
    except HTTPError as error:
        state = 'no_release' if error.code == 404 else 'unavailable'
        error.close()
        return UpdateResult(state)
    except (OSError, ValueError, TypeError, RecursionError):
        return UpdateResult('unavailable')


def updates_enabled(config):
    values = config.get('updates') if isinstance(config, dict) else None
    return isinstance(values, dict) and values.get('enabled') is True


@dataclass(frozen=True)
class UpdateEvent:
    generation: int
    result: UpdateResult


class UpdateController:
    """One daemon request at a time, with retired results dropped after opt-out.

    The optional request never joins the dictation worker or delays app shutdown.
    Cancellation stops queued checks and suppresses an in-flight result; its
    transport has a socket timeout and a bounded metadata body.
    """

    def __init__(self, callback, *, checker=check_updates, thread_factory=threading.Thread):
        self.callback, self.checker, self.thread_factory = callback, checker, thread_factory
        self._lock = threading.RLock()
        self._generation = 0
        self._enabled = self._closed = self._pending = False
        self._active = None
        self._result = UpdateResult()

    @property
    def result(self):
        with self._lock:
            return self._result

    @property
    def enabled(self):
        with self._lock:
            return self._enabled and not self._closed

    def is_current(self, event):
        with self._lock:
            return not self._closed and event.generation == self._generation and event.result is self._result

    def _publish(self, result):
        self._result = result
        try:
            self.callback(UpdateEvent(self._generation, result))
        except RuntimeError:  # A closed Qt receiver must not keep a request alive.
            pass

    def configure(self, enabled):
        enabled = enabled is True
        with self._lock:
            if self._closed or enabled == self._enabled:
                return False
            self._enabled = enabled
            self._generation += 1
            self._pending = enabled and self._active is not None
            self._publish(UpdateResult('checking' if enabled else 'disabled'))
        if enabled:
            self.check()
        return True

    def check(self):
        with self._lock:
            if self._closed or not self._enabled or self._active is not None:
                return False
            self._generation += 1
            token = self._generation
            self._active, self._pending = token, False
            self._publish(UpdateResult('checking'))
            try:
                thread = self.thread_factory(target=lambda: self._run(token), name='Saydraft-update-check', daemon=True)
                thread.start()
            except Exception:
                self._active = None
                self._publish(UpdateResult('unavailable'))
                return False
        return True

    def _cancelled(self, token):
        with self._lock:
            return self._closed or not self._enabled or token != self._generation

    def _run(self, token):
        try:
            result = self.checker(enabled=True, cancelled=lambda: self._cancelled(token))
            if not isinstance(result, UpdateResult):
                result = UpdateResult('unavailable')
        except Exception:
            result = UpdateResult('unavailable')
        with self._lock:
            self._active = None
            if not self._cancelled(token):
                self._publish(result)
            again = self._pending and self._enabled and not self._closed
            self._pending = False
        if again:
            self.check()

    def close(self):
        with self._lock:
            self._closed = True
            self._enabled = self._pending = False
            self._generation += 1
