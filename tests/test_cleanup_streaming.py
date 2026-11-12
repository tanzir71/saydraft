import json
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from saydraft.cleanup.llm.client import CleanupClient
from saydraft.cleanup.llm.loopback import LocalHTTPError
from saydraft.cleanup.llm.sidecar import SidecarReply
from saydraft.cleanup.llm.streaming import event_data, read_completion


def frame(content=None, finish=None, **delta):
    if content is not None:
        delta["content"] = content
    data = {"choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
    return b"data: " + json.dumps(data, ensure_ascii=False).encode("utf-8") + b"\r\n\r\n"


DONE = b"data: [DONE]\r\n\r\n"


def test_utf8_bom_crlf_multiline_data_and_byte_fragmentation():
    expected = "বাংলা مرحبًا"
    first = json.dumps({"choices": [{"delta": {"content": expected}, "finish_reason": None}]}, ensure_ascii=False)
    first = first.replace('"choices": [', '"choices":\r\ndata: [')
    raw = b"\xef\xbb\xbf: heartbeat\r\nid: 7\r\ndata: " + first.encode("utf-8") + b"\r\n\r\n" + frame(finish="stop") + DONE
    result = read_completion([raw[index:index + 1] for index in range(len(raw))])
    assert result == {"text": expected, "finish_reason": "stop", "done": True, "tool_calls": False}


def test_reasoning_is_not_collected_and_tool_requests_remain_metadata_only():
    result = read_completion([frame(reasoning_content="not output"), frame("Visible words"),
                              frame(finish="tool_calls", tool_calls=[{"id": "fixture"}]), DONE])
    assert result["text"] == "Visible words" and result["tool_calls"]
    assert "not output" not in repr(result)


@pytest.mark.parametrize("raw", [b"data: {broken}\n\n", b"data: \xff\n\n",
    frame("word", finish="stop") + frame("after completion") + DONE,
    b'data: {"choices": [1]}\n\n', b'data: {"error": "private body"}\n\n'])
def test_malformed_stream_never_includes_raw_response_in_error(raw):
    with pytest.raises(LocalHTTPError) as caught:
        read_completion([raw])
    assert "private body" not in str(caught.value) and "{broken}" not in str(caught.value)


def test_unterminated_event_is_not_dispatched_and_oversized_lines_are_rejected():
    assert list(event_data([b"data: incomplete"])) == []
    with pytest.raises(LocalHTTPError, match="size"):
        list(event_data([b"data: " + b"x" * 65537]))


class FakeModel:
    def __init__(self, chunks, *, tokens=None):
        self.chunks = chunks
        self.tokens = tokens if tokens is not None else list(range(8))
        self.requests, self.closed = [], False

    def request_json(self, path, **kwargs):
        self.requests.append((path, kwargs))
        return {"tokens": self.tokens}

    @contextmanager
    def response_bytes(self, path, **kwargs):
        self.requests.append((path, kwargs))
        try:
            yield iter(self.chunks)
        finally:
            self.closed = True


def cleaner(model, *, max_tokens=256):
    def run(operation, *, timeout):
        try:
            return SidecarReply(operation(model, 5 + timeout), "ok")
        except TimeoutError:
            return SidecarReply(None, "timeout")
        except LocalHTTPError:
            return SidecarReply(None, "unavailable")

    return CleanupClient(SimpleNamespace(run=run), max_tokens=max_tokens, clock=lambda: 5)


def test_fake_llm_receives_text_contract_and_complete_plain_text_is_returned_without_json_decoding():
    model = FakeModel([frame("What is the capital "), frame("of France?"), frame(finish="stop"), DONE])
    result = cleaner(model).clean("what is the capital of France")
    assert result.text == "What is the capital of France?" and result.reason == "ok"
    path, call = model.requests[1]
    payload = call["payload"]
    assert path == "/v1/chat/completions" and call["content_type"] == "text/event-stream"
    assert payload["stream"] and payload["temperature"] == 0 and payload["max_tokens"] == 26
    assert payload["stop"] == ["</out>"] and "response_format" not in payload
    assert payload["chat_template_kwargs"] == {"enable_thinking": False}
    assert model.requests[0][1]["deadline"] == call["deadline"] and model.closed


@pytest.mark.parametrize("chunks,reason", [
    ([frame("available partial")], "incomplete"),
    ([frame("limited", finish="length"), DONE], "incomplete"),
    ([frame("no finish marker"), DONE], "incomplete"),
    ([frame(finish="stop"), DONE], "empty"),
    ([frame("tool", finish="stop", tool_calls=[{}]), DONE], "tool_output"),
])
def test_partial_length_limited_empty_or_tool_output_never_becomes_cleanup_text(chunks, reason):
    model = FakeModel(chunks)
    result = cleaner(model).clean("original words")
    assert result.text is None and result.reason == reason and model.closed


def test_complete_protected_tokens_restore_but_missing_or_invented_ones_are_refused():
    model = FakeModel([frame("Send ⟦T0⟧ to ⟦T1⟧."), frame(finish="stop"), DONE])
    result = cleaner(model).clean("send __GLOSSARY_0__ to __SPAN_0__")
    assert result.text == "Send __GLOSSARY_0__ to __SPAN_0__."
    model = FakeModel([frame("Send ⟦T0⟧."), frame(finish="stop"), DONE])
    result = cleaner(model).clean("send __GLOSSARY_0__ to __SPAN_0__")
    assert result.text is None and result.reason == "protected_changed"


def test_configured_output_cap_and_invalid_tokenizer_result_are_enforced():
    model = FakeModel([frame("words"), frame(finish="stop"), DONE], tokens=list(range(100)))
    assert cleaner(model, max_tokens=32).clean("words").output_limit == 32
    model = FakeModel([], tokens=[True])
    assert cleaner(model).clean("words").text is None and len(model.requests) == 1


def test_deadline_is_checked_during_decoding_without_publishing_a_partial():
    def expired():
        raise TimeoutError("fixture deadline")

    with pytest.raises(TimeoutError):
        read_completion([frame("available words"), frame(finish="stop"), DONE], check=expired)
