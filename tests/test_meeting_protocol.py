import io
import json
import queue
import struct

import numpy as np
import pytest

from saydraft.audio.devices import InputSelection
from saydraft.meetings.protocol import (
    AUDIO, END, ERROR, READY, START, HEADER, MAGIC, MAX_PAYLOAD, PCM_HEADER,
    CaptureDecoder, PacketWriter, audio_frame, frame, json_frame,
)
from saydraft.meetings.request import CaptureRequest


def starts():
    return [json_frame(START, {'track': track, 'offset_seconds': offset})
            for track, offset in (('microphone', .01), ('desktop', .025))] + [json_frame(READY, {})]


def complete_packets():
    return starts() + [audio_frame('microphone', 0, np.full(1600, .125, dtype=np.float32)),
        audio_frame('desktop', 0, np.full(1584, -.25, dtype=np.float32)),
        audio_frame('desktop', 1584, np.full(16, -.5, dtype=np.float32)),
        json_frame(END, {'complete': True, 'reason': 'stopped', 'frames': {'microphone': 1600, 'desktop': 1600}})]


def feed(decoder, packets, *, chunk=4096):
    for packet in packets:
        for offset in range(0, len(packet), chunk):
            decoder.feed(packet[offset:offset + chunk])


@pytest.mark.parametrize('chunk', [1, 7, 4096])
def test_pcm_stream_preserves_separate_tracks_counts_tail_and_readonly_aligned_audio(chunk):
    events = []
    decoder = CaptureDecoder(events.append)
    feed(decoder, complete_packets(), chunk=chunk)
    end = decoder.finish()
    assert end.complete and (end.microphone_frames, end.desktop_frames) == (1600, 1600)
    audio = [event.value for event in events if event.kind == 'audio']
    assert [(part.track, part.start_frame, len(part.samples)) for part in audio] == [
        ('microphone', 0, 1600), ('desktop', 0, 1584), ('desktop', 1584, 16)]
    assert all(part.samples.flags.aligned and not part.samples.flags.writeable for part in audio)
    np.testing.assert_array_equal(audio[0].samples, np.full(1600, .125, dtype=np.float32))
    assert events[0].value.offset_seconds == .01 and events[1].value.offset_seconds == .025
    with pytest.raises(ValueError, match='retired'):
        decoder.feed(b'new bytes')


def test_packet_writer_handles_short_writes_without_interleaving_or_truncation():
    class Short(io.BytesIO):
        def write(self, data):
            return super().write(data[:7])
    output = Short()
    writer = PacketWriter(output)
    packets = complete_packets()
    for packet in packets:
        writer.write(packet)
    assert output.getvalue() == b''.join(packets)


@pytest.mark.parametrize('result', [None, 0, -1, True, 1000000])
def test_broken_pipe_writes_fail_without_spinning(result):
    class Broken:
        def write(self, _data): return result
        def flush(self): pass
    with pytest.raises(OSError, match='stopped accepting'):
        PacketWriter(Broken()).write(starts()[0])


def test_corruption_is_sticky_and_releases_the_incomplete_buffer():
    packet = bytearray(starts()[0])
    packet[-1] ^= 1
    decoder = CaptureDecoder(lambda _event: None)
    with pytest.raises(ValueError, match='Corrupted'):
        decoder.feed(bytes(packet))
    assert decoder.failed and not decoder._pending
    with pytest.raises(ValueError, match='retired'):
        decoder.feed(starts()[0])


@pytest.mark.parametrize('packet', [HEADER.pack(MAGIC, START, MAX_PAYLOAD + 1, 0),
    HEADER.pack(b'BAD1', START, 1, 0), HEADER.pack(MAGIC, 255, 1, 0),
    HEADER.pack(MAGIC, START, 0, 0), b'x' * 4097])
def test_headers_and_input_chunks_are_bounded_before_growing_a_recording_buffer(packet):
    decoder = CaptureDecoder(lambda _event: None)
    with pytest.raises(ValueError):
        decoder.feed(packet)
    assert not decoder._pending


@pytest.mark.parametrize('packet', [
    json_frame(START, {'track': 'microphone', 'offset_seconds': 0}),
    json_frame(READY, {}),
    audio_frame('microphone', 1, np.zeros(16, dtype=np.float32)),
    frame(AUDIO, PCM_HEADER.pack(1, 0) + struct.pack('<f', float('nan'))),
    frame(START, b'{"track":"microphone","track":"desktop","offset_seconds":0}'),
    json_frame(END, {'complete': True, 'reason': 'stopped', 'frames': {'microphone': True, 'desktop': 0}}),
])
def test_duplicate_control_missing_samples_nonfinite_pcm_and_forged_completion_are_refused(packet):
    decoder = CaptureDecoder(lambda _event: None)
    feed(decoder, starts())
    with pytest.raises(ValueError):
        feed(decoder, [packet])


def test_valid_frames_without_an_end_receipt_cannot_be_a_complete_recording():
    decoder = CaptureDecoder(lambda _event: None)
    feed(decoder, complete_packets()[:-1])
    with pytest.raises(ValueError, match='Incomplete'):
        decoder.finish()


def test_error_cannot_be_overridden_by_a_later_success_receipt():
    decoder = CaptureDecoder(lambda _event: None)
    packets = complete_packets()
    feed(decoder, packets[:-1] + [json_frame(ERROR, {'reason': 'audio_gap'})])
    with pytest.raises(ValueError, match='Inconsistent'):
        feed(decoder, packets[-1:])


def test_backpressure_never_counts_an_undelivered_audio_chunk():
    def full(event):
        if event.kind == 'audio':
            raise queue.Full()
    decoder = CaptureDecoder(full)
    feed(decoder, starts())
    with pytest.raises(queue.Full):
        feed(decoder, complete_packets()[3:4])
    assert decoder.frames == {'microphone': 0, 'desktop': 0} and decoder.failed


def test_data_after_end_and_truncated_last_packets_are_not_accepted():
    decoder = CaptureDecoder(lambda _event: None)
    feed(decoder, complete_packets())
    with pytest.raises(ValueError):
        decoder.feed(b'x')
    other = CaptureDecoder(lambda _event: None)
    feed(other, complete_packets()[:-1] + [complete_packets()[-1][:-1]])
    with pytest.raises(ValueError, match='Incomplete'):
        other.finish()


def test_capture_request_round_trips_unicode_without_dynamic_paths_or_unknown_fields():
    request = CaptureRequest(True, InputSelection('বাংলা العربية fixture', 'Windows WASAPI'), 'render-id', 1800)
    assert CaptureRequest.from_json(request.to_json()) == request
    value = json.loads(request.to_json())
    value['download'] = True
    with pytest.raises(ValueError):
        CaptureRequest.from_json(json.dumps(value))


@pytest.mark.parametrize('value', [True, 0, -1, 7201, 30.0, '30'])
def test_capture_duration_requires_a_bounded_integer(value):
    with pytest.raises(ValueError):
        CaptureRequest(consent=True, max_seconds=value)


def test_unconfirmed_oversized_and_malformed_device_requests_cannot_reach_a_helper():
    with pytest.raises(PermissionError):
        CaptureRequest().to_json()
    for endpoint in ('bad\0id', '\ud800'):
        with pytest.raises(ValueError):
            CaptureRequest(consent=True, desktop_endpoint=endpoint)
    oversized = CaptureRequest(True, InputSelection('🌏' * 512, '🌏' * 512), '🌏' * 1024)
    with pytest.raises(ValueError, match='transport limit'):
        oversized.to_json()
    with pytest.raises(ValueError):
        CaptureRequest.from_json('{"consent":true,"consent":false}')
