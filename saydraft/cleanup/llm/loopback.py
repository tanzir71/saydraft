"""Bounded authenticated JSON requests to our own IPv4 loopback sidecar only."""

from __future__ import annotations

import http.client
import json
import math
import re
import socket
import threading
import time
from contextlib import contextmanager

MAX_JSON_BYTES = 1024 * 1024
_GET = frozenset(("/health", "/v1/models"))
_POST = frozenset(("/completion", "/v1/chat/completions", "/tokenize"))


class LocalHTTPError(RuntimeError):
    """Metadata-only failure; never includes a response, prompt or API key."""


def _reject_constant(value):
    raise ValueError("Nonfinite JSON values are not supported")


class LoopbackClient:
    def __init__(self, port, api_key, *, clock=time.monotonic):
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("Local server port is invalid")
        if not isinstance(api_key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", api_key):
            raise ValueError("Local authentication key is invalid")
        self._port, self._key, self._clock = port, api_key, clock

    @contextmanager
    def response_bytes(self, path, *, payload=None, deadline, content_type="application/json"):
        if content_type not in ("application/json", "text/event-stream"):
            raise ValueError("Unsupported local response type")
        if path not in (_GET if payload is None else _POST):
            raise ValueError("Unsupported local server endpoint")
        remaining = deadline - self._clock()
        if not math.isfinite(remaining) or remaining <= 0:
            raise TimeoutError("Local request deadline expired")
        body = None if payload is None else json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        if body is not None and len(body) > MAX_JSON_BYTES:
            raise ValueError("Local request exceeds its size limit")
        connection = http.client.HTTPConnection("127.0.0.1", self._port, timeout=remaining)
        expired = threading.Event()
        abort_socket = response = None

        def expire():
            expired.set()
            if abort_socket is not None:
                try:
                    abort_socket.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

        timer = threading.Timer(remaining, expire)
        timer.daemon = True
        timer.start()
        try:
            connection.connect()
            # Keep a duplicate for deadline shutdown even when HTTPConnection
            # relinquishes its socket to a Connection: close response body.
            abort_socket = connection.sock.dup()
            if expired.is_set() or self._clock() >= deadline:
                raise TimeoutError("Local request deadline expired")
            connection.request("GET" if payload is None else "POST", path, body=body, headers={
                "Authorization": f"Bearer {self._key}", "Content-Type": "application/json; charset=utf-8",
                "Accept": content_type, "Connection": "close"})
            response = connection.getresponse()
            if response.status != 200:
                raise LocalHTTPError(f"Local server returned HTTP {response.status}")
            actual_type = response.getheader("Content-Type", "").split(";", 1)[0].strip().lower()
            if actual_type != content_type:
                raise LocalHTTPError("Local server returned an unsupported content type")
            length = response.getheader("Content-Length")
            if length is not None and (not length.isdecimal() or int(length) > MAX_JSON_BYTES):
                raise LocalHTTPError("Local response exceeds its size limit")

            def chunks():
                size = 0
                while True:
                    if expired.is_set() or self._clock() >= deadline:
                        raise TimeoutError("Local request deadline expired")
                    chunk = response.read1(min(64 * 1024, MAX_JSON_BYTES + 1 - size))
                    if expired.is_set() or self._clock() >= deadline:
                        raise TimeoutError("Local request deadline expired")
                    if not chunk:
                        return
                    size += len(chunk)
                    if size > MAX_JSON_BYTES:
                        raise LocalHTTPError("Local response exceeds its size limit")
                    yield chunk

            yield chunks()
            if expired.is_set() or self._clock() >= deadline:
                raise TimeoutError("Local request deadline expired")
        except (OSError, http.client.HTTPException) as error:
            if expired.is_set() or self._clock() >= deadline or isinstance(error, TimeoutError):
                raise TimeoutError("Local request deadline expired") from None
            raise LocalHTTPError("Local server connection failed") from None
        finally:
            timer.cancel()
            if response is not None:
                response.close()
            connection.close()
            if abort_socket is not None:
                abort_socket.close()

    def request_json(self, path, *, payload=None, deadline):
        with self.response_bytes(path, payload=payload, deadline=deadline) as chunks:
            try:
                result = json.loads(b"".join(chunks).decode("utf-8"), parse_constant=_reject_constant)
            except (UnicodeError, ValueError):
                raise LocalHTTPError("Local server returned invalid JSON") from None
            if not isinstance(result, dict):
                raise LocalHTTPError("Local server returned an unsupported JSON value")
            return result
