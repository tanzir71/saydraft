import json

import pytest

from tools.soak_native import StreamEvidence


def stream(*, finish='length', content='বাংলা العربية', tools=False):
    choice = {'index': 0, 'delta': {'content': content}, 'finish_reason': None}
    if tools:
        choice['delta']['tool_calls'] = [{'id': 'fixture'}]
    values = [{'choices': [choice]}, {'choices': [{'index': 0, 'delta': {}, 'finish_reason': finish}]}]
    return b''.join(b'data: '+json.dumps(value, ensure_ascii=False).encode()+b'\r\n\r\n' for value in values)+b'data: [DONE]\r\n\r\n'


def test_stream_evidence_survives_utf8_and_crlf_split_at_every_byte():
    tap = StreamEvidence()
    for value in stream():
        tap.feed(bytes([value]))
    assert tap.complete and not tap.invalid


@pytest.mark.parametrize('wire', [
    stream(finish='stop'), stream(content=''), stream(tools=True),
    stream().replace(b'data: [DONE]\r\n\r\n', b''),
    b'data: {"choices": "invalid"}\n\ndata: [DONE]\n\n',
    b'data: {"choices": [{"delta": {"content": 42}, "finish_reason": "length"}]}\n\ndata: [DONE]\n\n',
])
def test_incomplete_tool_or_invalid_stream_cannot_earn_normal_generation_credit(wire):
    tap = StreamEvidence()
    tap.feed(wire)
    assert not tap.complete
