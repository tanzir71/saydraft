"""Bounded UTF-8 SSE decoding; partial words never leave the completion buffer."""

import codecs
import json

from .loopback import MAX_JSON_BYTES, LocalHTTPError, _reject_constant

MAX_EVENT_CHARS = 64 * 1024


def event_data(chunks, check=lambda: None):
    decoder = codecs.getincrementaldecoder("utf-8-sig")()
    line, data, last_cr, total, event_chars = [], [], False, 0, 0
    try:
        for chunk in chunks:
            check()
            total += len(chunk)
            if total > MAX_JSON_BYTES:
                raise LocalHTTPError("Local stream exceeds its size limit")
            for char in decoder.decode(chunk):
                if last_cr:
                    last_cr = False
                    if char == "\n":
                        continue
                if char not in "\r\n":
                    line.append(char)
                    if len(line) > MAX_EVENT_CHARS:
                        raise LocalHTTPError("Local stream line exceeds its size limit")
                    continue
                check()
                last_cr = char == "\r"
                value = "".join(line)
                line.clear()
                if not value:
                    if data:
                        yield "\n".join(data)
                        data.clear()
                        event_chars = 0
                elif value.startswith("data:"):
                    part = value[5:].removeprefix(" ")
                    event_chars += len(part)
                    if event_chars > MAX_EVENT_CHARS:
                        raise LocalHTTPError("Local stream event exceeds its size limit")
                    data.append(part)
        decoder.decode(b"", final=True)
        # EOF does not dispatch an unterminated event (SSE contract).
    except UnicodeError:
        raise LocalHTTPError("Local stream contains invalid UTF-8") from None


def read_completion(chunks, check=lambda: None):
    pieces, finish, done, tools = [], None, False, False
    for data in event_data(chunks, check):
        check()
        if data == "[DONE]":
            done = True
            break
        try:
            event = json.loads(data, parse_constant=_reject_constant)
        except ValueError:
            raise LocalHTTPError("Local stream contains invalid JSON") from None
        if not isinstance(event, dict) or "error" in event:
            raise LocalHTTPError("Local stream reported an invalid event")
        choices = event.get("choices", [])
        if not isinstance(choices, list) or len(choices) > 1:
            raise LocalHTTPError("Local stream returned unsupported choices")
        if not choices:
            continue  # Optional usage-only event.
        choice = choices[0]
        if not isinstance(choice, dict) or choice.get("index", 0) != 0:
            raise LocalHTTPError("Local stream returned an unsupported choice")
        delta = choice.get("delta", {})
        if not isinstance(delta, dict) or delta.get("role", "assistant") != "assistant":
            raise LocalHTTPError("Local stream returned an unsupported delta")
        content = delta.get("content")
        if content is not None and not isinstance(content, str):
            raise LocalHTTPError("Local stream returned unsupported content")
        reason = choice.get("finish_reason")
        if reason is not None and not isinstance(reason, str) or finish is not None and (content or reason):
            raise LocalHTTPError("Local stream continued after completion")
        if content:
            pieces.append(content)
        tools = tools or bool(delta.get("tool_calls") or delta.get("function_call"))
        if reason is not None:
            finish = reason
        # Reasoning fields are deliberately not accumulated or published.
    check()
    return {"text": "".join(pieces), "finish_reason": finish, "done": done, "tool_calls": tools}
