"""Shared capture/analysis bounds, including admitted final PCM packets."""

from .audio import SAMPLE_RATE
from .request import MAX_SECONDS

MAX_AUDIO_SAMPLES = 1600
TRACK_SEPARATOR_SAMPLES = SAMPLE_RATE


def track_frame_limit(max_seconds=MAX_SECONDS):
    if type(max_seconds) is not int or not 1 <= max_seconds <= MAX_SECONDS:
        raise ValueError('Invalid meeting duration bound')
    return max_seconds * SAMPLE_RATE + MAX_AUDIO_SAMPLES


MAX_ANALYSIS_SAMPLES = 2 * track_frame_limit() + TRACK_SEPARATOR_SAMPLES
