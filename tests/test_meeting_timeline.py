import numpy as np
import pytest

from saydraft.meetings.limits import MAX_ANALYSIS_SAMPLES, track_frame_limit
from saydraft.meetings.process import CaptureOutcome
from saydraft.meetings.protocol import AudioChunk, CaptureEnd, CaptureEvent, TrackStarted
from saydraft.meetings.timeline import MeetingAudioBuffer


def captured(microphone, desktop, *, offsets=(0., 0.), complete=True):
    maximum = max(1, int(np.ceil(max(len(microphone), len(desktop)) / 16000)))
    buffer = MeetingAudioBuffer(max_seconds=maximum)
    for track, offset in zip(('microphone', 'desktop'), offsets, strict=True):
        buffer.consume(CaptureEvent('track', TrackStarted(track, offset)))
    buffer.consume(CaptureEvent('ready'))
    for track, waveform in (('microphone', microphone), ('desktop', desktop)):
        for start in range(0, len(waveform), 1600):
            buffer.consume(CaptureEvent('audio', AudioChunk(track, start, waveform[start:start + 1600])))
    end = CaptureEnd(complete, 'stopped' if complete else 'capture_failed', len(microphone), len(desktop))
    buffer.consume(CaptureEvent('end', end))
    return buffer.freeze(CaptureOutcome(True, complete, end.reason, 0 if complete else 2, end=end))


def test_tracks_share_one_contiguous_read_only_analysis_allocation_without_mixing_samples():
    mic, desktop = np.linspace(-.5, .5, 2400, dtype=np.float32), np.full(1600, .8, np.float32)
    result = captured(mic, desktop, offsets=(.1, .3))
    assert result.complete and not result.issues
    assert result.samples.dtype == np.float32 and not result.samples.flags.writeable
    assert np.array_equal(result.waveform(result.tracks[0]), mic)
    assert np.array_equal(result.waveform(result.tracks[1]), desktop)
    assert np.count_nonzero(result.samples[2400:18400]) == 0
    assert np.shares_memory(result.waveform(result.tracks[1]), result.samples)
    assert result.duration == .4


def test_admitted_audio_is_copied_and_tiny_packets_have_bounded_storage_object_count():
    buffer = MeetingAudioBuffer(max_seconds=2)
    buffer.consume(CaptureEvent('track', TrackStarted('microphone', 0.)))
    sample = np.array([.25], np.float32)
    for index in range(16001):
        buffer.consume(CaptureEvent('audio', AudioChunk('microphone', index, sample)))
    sample[:] = 5
    assert len(buffer._parts['microphone']) <= 2
    result = buffer.freeze(CaptureOutcome(True, False, 'unexpected_exit'))
    assert np.all(result.samples == .25) and len(result.samples) == 16001
    assert not result.complete and result.issues == ('incomplete_capture',)


def test_stop_intent_is_not_a_barrier_for_freezing_and_complete_counts_must_agree():
    buffer = MeetingAudioBuffer(max_seconds=1)
    with pytest.raises(RuntimeError, match='stopped'):
        buffer.freeze(CaptureOutcome(False, False, 'stop_unconfirmed'))
    with pytest.raises(ValueError, match='inconsistent'):
        buffer.freeze(CaptureOutcome(True, True, 'stopped'))
    assert not buffer.freeze(CaptureOutcome(True, False, 'cancelled')).samples.size
    with pytest.raises(RuntimeError, match='retired'):
        buffer.consume(CaptureEvent('ready'))


def test_sample_limits_include_both_final_packets_and_the_track_separator():
    assert MAX_ANALYSIS_SAMPLES == 2 * track_frame_limit() + 16000
    buffer = MeetingAudioBuffer(max_seconds=1)
    buffer.consume(CaptureEvent('track', TrackStarted('microphone', 0.)))
    for offset in range(0, 17600, 1600):
        buffer.consume(CaptureEvent('audio', AudioChunk('microphone', offset, np.zeros(1600, np.float32))))
    with pytest.raises(ValueError, match='invalid'):
        buffer.consume(CaptureEvent('audio', AudioChunk('microphone', 17600, np.zeros(1, np.float32))))
    assert buffer.frames['microphone'] == 17600


@pytest.mark.parametrize('event', [
    CaptureEvent('track', TrackStarted('microphone', float('nan'))),
    CaptureEvent('ready'), CaptureEvent('unknown'),
    CaptureEvent('audio', AudioChunk('microphone', 0, np.ones(1, np.float32))),
    CaptureEvent('end', CaptureEnd(False, 'capture_failed', 1, 0)),
])
def test_invalid_order_or_metadata_never_silently_enters_the_timeline(event):
    with pytest.raises(ValueError):
        MeetingAudioBuffer(max_seconds=1).consume(event)


def test_gap_events_retain_partial_valid_audio_and_can_never_become_complete():
    buffer = MeetingAudioBuffer(max_seconds=1)
    buffer.consume(CaptureEvent('track', TrackStarted('desktop', .1)))
    buffer.consume(CaptureEvent('audio', AudioChunk('desktop', 0, np.ones(16, np.float32))))
    buffer.consume(CaptureEvent('error', 'audio_gap'))
    result = buffer.freeze(CaptureOutcome(True, False, 'transport_failed'))
    assert result.samples.size == 16 and result.issues == ('audio_gap', 'incomplete_capture')
    assert result.tracks[0].track == 'desktop'


def test_discard_retires_and_releases_all_owned_slabs():
    buffer = MeetingAudioBuffer(max_seconds=1)
    buffer.consume(CaptureEvent('track', TrackStarted('microphone', 0.)))
    buffer.consume(CaptureEvent('audio', AudioChunk('microphone', 0, np.ones(1600, np.float32))))
    buffer.discard()
    assert not any(buffer._parts.values())
    with pytest.raises(RuntimeError, match='retired'):
        buffer.freeze(CaptureOutcome(True, False, 'cancelled'))
