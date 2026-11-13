"""Bounded authenticated JSON requests to our own IPv4 loopback sidecar only."""

from __future__ import annotations

import http.client
import io
import json
import math
import re
import socket
import time
from contextlib import contextmanager
from functools import partial

MAX_JSON_BYTES = 1024 * 1024
_GET = frozenset(("/health", "/v1/models"))
_POST = frozenset(("/completion", "/v1/chat/completions", "/tokenize"))


class LocalHTTPError(RuntimeError):
    """Metadata-only failure; never includes a response, prompt or API key."""


def _reject_constant(value):
    raise ValueError("Nonfinite JSON values are not supported")


def _remaining(deadline, clock):
    seconds = deadline - clock()
    if not math.isfinite(seconds) or seconds <= 0:
        raise TimeoutError("Local request deadline expired")
    return seconds


class _DeadlineReader(io.RawIOBase):
    """Charge every underlying header/body read to the same deadline."""

    def __init__(self, raw, sock, deadline, clock):
        self._raw, self._sock, self._deadline, self._clock = raw, sock, deadline, clock

    def readable(self):
        return True

    def readinto(self, buffer):
        self._sock.settimeout(_remaining(self._deadline, self._clock))
        count = self._raw.readinto(buffer)
        _remaining(self._deadline, self._clock)
        return count

    def close(self):
        if not self.closed:
            try:
                self._raw.close()
            finally:
                super().close()


class _DeadlineResponse(http.client.HTTPResponse):
    def __init__(self, sock, *, deadline, clock, **kwargs):
        super().__init__(sock, **kwargs)
        # Keep SocketIO's reference counting: Connection: close can release the
        # connection while this file still owns its response socket.
        raw = self.fp.detach()
        self.fp = io.BufferedReader(_DeadlineReader(raw, sock, deadline, clock))


class _DeadlineConnection(http.client.HTTPConnection):
    def __init__(self, port, deadline, clock):
        super().__init__("127.0.0.1", port, timeout=_remaining(deadline, clock))
        self._deadline, self._clock = deadline, clock
        self.response_class = partial(_DeadlineResponse, deadline=deadline, clock=clock)

    def connect(self):
        # Literal IPv4 needs neither DNS nor a proxy. Recompute the budget after
        # request preparation instead of carrying an earlier socket timeout.
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.settimeout(_remaining(self._deadline, self._clock))
            sock.connect(("127.0.0.1", self.port))
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            _remaining(self._deadline, self._clock)
        except BaseException:
            sock.close()
            raise
        self.sock = sock

    def send(self, data):
        if self.sock is None:
            self.connect()
        self.sock.settimeout(_remaining(self._deadline, self._clock))
        super().send(data)
        _remaining(self._deadline, self._clock)


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
        _remaining(deadline, self._clock)
        body = None if payload is None else json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        if body is not None and len(body) > MAX_JSON_BYTES:
            raise ValueError("Local request exceeds its size limit")
        connection = _DeadlineConnection(self._port, deadline, self._clock)
        response = None
        try:
            connection.connect()
            connection.request("GET" if payload is None else "POST", path, body=body, headers={
                "Authorization": f"Bearer {self._key}", "Content-Type": "application/json; charset=utf-8",
                "Accept": content_type, "Connection": "close"})
            response = connection.getresponse()
            _remaining(deadline, self._clock)
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
                    _remaining(deadline, self._clock)
                    chunk = response.read1(min(64 * 1024, MAX_JSON_BYTES + 1 - size))
                    _remaining(deadline, self._clock)
                    if not chunk:
                        return
                    size += len(chunk)
                    if size > MAX_JSON_BYTES:
                        raise LocalHTTPError("Local response exceeds its size limit")
                    yield chunk

            yield chunks()
            _remaining(deadline, self._clock)
        except (OSError, http.client.HTTPException) as error:
            if self._clock() >= deadline or isinstance(error, TimeoutError):
                raise TimeoutError("Local request deadline expired") from None
            raise LocalHTTPError("Local server connection failed") from None
        finally:
            if response is not None:
                response.close()
            connection.close()

    def request_json(self, path, *, payload=None, deadline):
        with self.response_bytes(path, payload=payload, deadline=deadline) as chunks:
            try:
                result = json.loads(b"".join(chunks).decode("utf-8"), parse_constant=_reject_constant)
            except (UnicodeError, ValueError):
                raise LocalHTTPError("Local server returned invalid JSON") from None
            if not isinstance(result, dict):
                raise LocalHTTPError("Local server returned an unsupported JSON value")
            return result
