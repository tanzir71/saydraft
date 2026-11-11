import json
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from saydraft.cleanup.llm.loopback import MAX_JSON_BYTES, LocalHTTPError, LoopbackClient
from saydraft.privacy.netguard import NetworkGuard

KEY = "fixture_key_1234567890"


@contextmanager
def local_server(mode="normal"):
    received = []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args):
            pass

        def do_GET(self):
            self.respond()

        def do_POST(self):
            self.respond()

        def respond(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            received.append((self.path, self.headers.get("Authorization"), body))
            try:
                if mode == "slow_header":
                    for byte in b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{}":
                        self.connection.sendall(bytes([byte]))
                        time.sleep(0.02)
                    return
                response = json.dumps({"value": "বাংলা العربية", "echo": json.loads(body) if body else None},
                                      ensure_ascii=False).encode("utf-8")
                status = 401 if self.headers.get("Authorization") != f"Bearer {KEY}" else 200
                if mode in ("error", "redirect"):
                    status = 500 if mode == "error" else 302
                    response = b"private response content must not appear in exceptions"
                if mode == "invalid":
                    response = b'{"value": NaN}'
                if mode == "array":
                    response = b"[]"
                if mode == "large_body":
                    response = b"x" * (MAX_JSON_BYTES + 64 * 1024)
                self.send_response(status)
                self.send_header("Content-Type", "text/html" if mode == "html" else "application/json; charset=utf-8")
                if mode != "large_body":
                    self.send_header("Content-Length", str(MAX_JSON_BYTES + 1 if mode == "large_header" else len(response)))
                self.send_header("Connection", "close")
                if mode == "redirect":
                    self.send_header("Location", "https://example.com/")
                self.end_headers()
                if mode == "dribble":
                    for byte in response:
                        self.wfile.write(bytes([byte]))
                        self.wfile.flush()
                        time.sleep(0.02)
                else:
                    self.wfile.write(response)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass  # The deadline test intentionally interrupts a local fixture response.

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)
    thread.start()
    try:
        yield server.server_port, received
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_authenticated_utf8_loopback_works_under_network_guard_and_ignores_proxy_env(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://unreachable.invalid:9")
    with local_server() as (port, received):
        NetworkGuard.install()
        try:
            client = LoopbackClient(port, KEY)
            assert client.request_json("/health", deadline=time.monotonic() + 2)["value"] == "বাংলা العربية"
            payload = {"text": "literal words", "stream": False}
            assert client.request_json("/completion", payload=payload, deadline=time.monotonic() + 2)["echo"] == payload
        finally:
            NetworkGuard.uninstall()
    assert len(received) == 2 and all(row[1] == f"Bearer {KEY}" for row in received)


@pytest.mark.parametrize("mode", ["error", "redirect", "invalid", "array", "html", "large_header", "large_body"])
def test_invalid_status_json_or_oversized_response_fails_without_body_or_secret_exposure(mode):
    with local_server(mode) as (port, received):
        with pytest.raises(LocalHTTPError) as caught:
            LoopbackClient(port, KEY).request_json("/health", deadline=time.monotonic() + 2)
    assert len(received) == 1
    assert KEY not in str(caught.value) and "private response content" not in str(caught.value)


@pytest.mark.parametrize("mode", ["dribble", "slow_header"])
def test_absolute_deadline_interrupts_trickled_body_and_headers(mode):
    with local_server(mode) as (port, received):
        started = time.monotonic()
        with pytest.raises(TimeoutError):
            LoopbackClient(port, KEY).request_json("/health", deadline=started + 0.12)
        elapsed = time.monotonic() - started
    assert elapsed < 0.7 and len(received) == 1


def test_authentication_failure_is_rejected():
    with local_server() as (port, received):
        with pytest.raises(LocalHTTPError, match="401"):
            LoopbackClient(port, "wrong_fixture_key_12345").request_json("/health", deadline=time.monotonic() + 2)


def test_non_loopback_endpoints_and_invalid_configuration_cannot_connect():
    client = LoopbackClient(1, KEY)
    with pytest.raises(ValueError, match="endpoint"):
        client.request_json("https://example.com/", deadline=time.monotonic() + 1)
    with pytest.raises(ValueError, match="endpoint"):
        client.request_json("/health", payload={}, deadline=time.monotonic() + 1)
    with pytest.raises(TimeoutError):
        client.request_json("/health", deadline=time.monotonic() - 1)
    with pytest.raises(ValueError, match="size"):
        client.request_json("/completion", payload={"text": "x" * MAX_JSON_BYTES}, deadline=time.monotonic() + 1)
    with pytest.raises(ValueError):
        LoopbackClient(True, KEY)
    with pytest.raises(ValueError):
        LoopbackClient(1, KEY + "\r\nBad: header")
