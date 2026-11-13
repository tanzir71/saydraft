"""Process-wide Python socket policy: loopback and explicit scoped exceptions.

This guards Python socket APIs, not native extensions or child processes. Use an
OS firewall rule for that boundary (see the distribution/privacy milestone).
"""

from __future__ import annotations

import ipaddress
import logging
import socket
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
from collections.abc import Iterable

logger = logging.getLogger(__name__)


class NetworkBlockedError(PermissionError):
    """An operation attempted to use a non-authorized network destination."""


@dataclass
class _DownloadScope:
    hosts: frozenset[str]
    resolved: set[str] = field(default_factory=set)


_scope: ContextVar[_DownloadScope | None] = ContextVar("saydraft_download_scope", default=None)


def _host(value) -> str:
    if isinstance(value, bytes):
        value = value.decode("ascii", errors="strict")
    return str(value).lower().rstrip(".")


def _is_loopback(host: str) -> bool:
    try:
        address = ipaddress.ip_address(host)
        return address.is_loopback or bool(
            isinstance(address, ipaddress.IPv6Address)
            and address.ipv4_mapped and address.ipv4_mapped.is_loopback
        )
    except ValueError:
        return False


def _check(host, *, dns: bool = False) -> None:
    name = _host(host)
    if _is_loopback(name) or name == "localhost":
        return
    scope = _scope.get()
    if scope is not None and (name in scope.hosts or (not dns and name in scope.resolved)):
        return
    logger.warning("Blocked outbound %s to host %s", "DNS" if dns else "connection", name[:253])
    raise NetworkBlockedError(f"Offline mode blocked network access to {name[:253]}")


class NetworkGuard:
    _lock = threading.RLock()
    _originals: dict[tuple[object, str], object] = {}

    @classmethod
    def is_installed(cls) -> bool:
        with cls._lock:
            return bool(cls._originals)

    @classmethod
    def install(cls) -> None:
        """Install once, before loading workers and optional model libraries."""
        with cls._lock:
            if cls._originals:
                return

            def patch(owner, name, wrapper):
                original = getattr(owner, name)
                cls._originals[owner, name] = original
                setattr(owner, name, wrapper(original))

            def address_call(original):
                @wraps(original)
                def guarded(sock, address, *args, **kwargs):
                    if sock.family in (socket.AF_INET, socket.AF_INET6):
                        _check(address[0])
                    return original(sock, address, *args, **kwargs)
                return guarded

            def resolve_call(original):
                @wraps(original)
                def guarded(host, *args, **kwargs):
                    _check(host, dns=True)
                    results = original(host, *args, **kwargs)
                    name = _host(host)
                    scope = _scope.get()
                    if name == "localhost":
                        if any(not _is_loopback(item[4][0]) for item in results):
                            raise NetworkBlockedError("localhost resolved outside loopback")
                    elif scope is not None and name in scope.hosts:
                        scope.resolved.update(item[4][0] for item in results)
                    return results
                return guarded

            def create_call(original):
                @wraps(original)
                def guarded(address, *args, **kwargs):
                    _check(address[0])
                    return original(address, *args, **kwargs)
                return guarded

            def datagram_call(original):
                @wraps(original)
                def guarded(sock, data, *args, **kwargs):
                    address = args[-1] if args else kwargs.get("address")
                    if sock.family in (socket.AF_INET, socket.AF_INET6) and address is not None:
                        _check(address[0])
                    return original(sock, data, *args, **kwargs)
                return guarded

            def legacy_dns_call(original):
                @wraps(original)
                def guarded(host, *args, **kwargs):
                    _check(host, dns=True)
                    # Use the guarded resolver so numeric results remain scoped.
                    socket.getaddrinfo(host, None)
                    return original(host, *args, **kwargs)
                return guarded

            patch(socket.socket, "connect", address_call)
            patch(socket.socket, "connect_ex", address_call)
            patch(socket.socket, "sendto", datagram_call)
            patch(socket, "getaddrinfo", resolve_call)
            patch(socket, "create_connection", create_call)
            patch(socket, "gethostbyname", legacy_dns_call)
            patch(socket, "gethostbyname_ex", legacy_dns_call)

    @classmethod
    def uninstall(cls) -> None:
        """Restore socket APIs for an isolated test or a completed app lifetime."""
        with cls._lock:
            for (owner, name), original in cls._originals.items():
                setattr(owner, name, original)
            cls._originals.clear()

    @staticmethod
    @contextmanager
    def allow_update_check():
        """Authorize only GitHub's API in the opted-in check's own context."""
        with NetworkGuard.allow_downloads({'api.github.com'}):
            yield

    @staticmethod
    @contextmanager
    def allow_downloads(manifest_hosts: Iterable[str]):
        """Authorize exact manifest hosts in the calling context, never globally.

        DNS results authorize numeric connections only for the same scope. New
        threads do not inherit permission. Redirect hosts need explicit entries.
        """
        if isinstance(manifest_hosts, (str, bytes)):
            raise ValueError("provide a collection of exact manifest hostnames")
        hosts = frozenset(_host(host) for host in manifest_hosts)
        if not hosts or any(
            not host or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789.-" for char in host)
            for host in hosts
        ):
            raise ValueError("download hosts must be exact hostnames, without wildcards or URLs")
        token = _scope.set(_DownloadScope(hosts))
        try:
            yield
        finally:
            _scope.reset(token)
