import socket
from concurrent.futures import ThreadPoolExecutor
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

import pytest

from saydraft.privacy.netguard import NetworkBlockedError, NetworkGuard

pytestmark = pytest.mark.offline


@pytest.fixture
def guard():
    NetworkGuard.install()
    try:
        yield
    finally:
        NetworkGuard.uninstall()


@pytest.mark.parametrize("host", ["example.com", "8.8.8.8", "192.168.1.2", "::ffff:8.8.8.8"])
@pytest.mark.parametrize("method", ["connect", "connect_ex"])
def test_external_connections_are_denied_before_os_connect(guard, host, method):
    with socket.socket() as sock, pytest.raises(NetworkBlockedError):
        getattr(sock, method)((host, 443))


def test_stray_urllib_request_raises(guard):
    # Avoid environment proxies so this exercises the actual requested host.
    with pytest.raises(URLError) as error:
        build_opener(ProxyHandler({})).open("https://example.com", timeout=0.1)
    assert isinstance(error.value.reason, NetworkBlockedError)


@pytest.mark.parametrize("resolver", ["getaddrinfo", "gethostbyname", "gethostbyname_ex"])
def test_dns_cannot_leak_outside_scope(guard, resolver):
    with pytest.raises(NetworkBlockedError):
        getattr(socket, resolver)("example.com", *([443] if resolver == "getaddrinfo" else []))


def test_udp_send_is_denied(guard):
    with socket.socket(type=socket.SOCK_DGRAM) as sock, pytest.raises(NetworkBlockedError):
        sock.sendto(b"no upload", ("8.8.8.8", 53))


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost"])
def test_loopback_connection_remains_usable(guard, host):
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        with socket.create_connection((host, server.getsockname()[1]), timeout=1) as client:
            connection, _address = server.accept()
            with connection:
                client.sendall(b"local")
                assert connection.recv(5) == b"local"


def test_scoped_download_hosts_resolve_without_real_network(monkeypatch):
    calls = []

    def resolver(host, port, *args, **kwargs):
        calls.append(host)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("203.0.113.5", port))]

    monkeypatch.setattr(socket, "getaddrinfo", resolver)
    NetworkGuard.install()
    try:
        with NetworkGuard.allow_downloads({"models.example"}):
            assert socket.getaddrinfo("models.example", 443)[0][4][0] == "203.0.113.5"
            with pytest.raises(NetworkBlockedError):
                socket.getaddrinfo("redirect.example", 443)
            with ThreadPoolExecutor() as executor:
                with pytest.raises(NetworkBlockedError):
                    executor.submit(socket.getaddrinfo, "models.example", 443).result()
        with pytest.raises(NetworkBlockedError):
            socket.getaddrinfo("models.example", 443)
        assert calls == ["models.example"]
    finally:
        NetworkGuard.uninstall()


def test_nested_scope_restores_permissions_after_error(guard):
    from saydraft.privacy.netguard import _check

    with NetworkGuard.allow_downloads({"outer.example"}):
        with pytest.raises(RuntimeError):
            with NetworkGuard.allow_downloads({"inner.example"}):
                _check("inner.example")
                with pytest.raises(NetworkBlockedError):
                    _check("outer.example")
                raise RuntimeError("cancelled download")
        _check("outer.example")
        with pytest.raises(NetworkBlockedError):
            _check("inner.example")
    with pytest.raises(NetworkBlockedError):
        _check("outer.example")


def test_fifty_synthetic_dictations_are_offline(guard):
    from tools.soak import SyntheticCycleRunner

    runner = SyntheticCycleRunner()
    for index in range(50):
        runner(index)


def test_install_is_idempotent_and_uninstall_restores_originals():
    original = socket.socket.connect
    NetworkGuard.install()
    wrapped = socket.socket.connect
    NetworkGuard.install()
    assert socket.socket.connect is wrapped
    NetworkGuard.uninstall()
    assert socket.socket.connect is original
