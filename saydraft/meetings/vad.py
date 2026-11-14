"""Meeting VAD uses retrospective segment bounds instead of delayed speech flags."""

import logging
from pathlib import Path

import numpy as np

from saydraft.audio.vad import SilenceTrimConfig, SpeechFrameDetector

logger = logging.getLogger(__name__)


def _create_detector(path):
    import sherpa_onnx as sherpa
    from saydraft.privacy.telemetry import disable_sherpa_telemetry

    disable_sherpa_telemetry(sherpa)
    config = sherpa.VadModelConfig()
    config.silero_vad.model = str(path)
    config.silero_vad.window_size = 512
    config.silero_vad.threshold = .5
    config.silero_vad.min_speech_duration = .1
    config.silero_vad.min_silence_duration = .6
    config.silero_vad.max_speech_duration = 20
    config.sample_rate, config.num_threads, config.provider = 16000, 1, 'cpu'
    return sherpa.VoiceActivityDetector(config, buffer_size_in_seconds=30)


class MeetingSileroVad:
    def __init__(self, model_path, *, factory=_create_detector):
        path = Path(model_path)
        if not path.is_file():
            raise FileNotFoundError('The meeting speech detection model is unavailable')
        self.detector = factory(path)

    def speech_ranges(self, waveform, *, check=lambda: None):
        self.detector.reset()
        ranges = []
        def collect():
            while not self.detector.empty():
                segment = self.detector.front
                start = max(0, int(segment.start) - 1920)
                end = min(len(waveform), int(segment.start) + len(segment.samples) + 1920)
                self.detector.pop()
                if start < end:
                    if ranges and start <= ranges[-1][1]:
                        ranges[-1] = (ranges[-1][0], max(ranges[-1][1], end))
                    else:
                        ranges.append((start, end))
        for offset in range(0, len(waveform), 512):
            check()
            frame = waveform[offset:offset + 512]
            if len(frame) < 512:
                frame = np.pad(frame, (0, 512 - len(frame)))
            self.detector.accept_waveform(frame)
            collect()
        check()
        self.detector.flush()
        collect()
        return tuple(ranges)


def meeting_detector():
    from saydraft.model_download import find_installed_model

    directory = find_installed_model('silero-vad-v5', check_hashes=True)
    if directory is not None:
        try:
            return MeetingSileroVad(directory / 'silero_vad.onnx')
        except Exception:
            logger.warning('Meeting speech detection unavailable; using the WebRTC fallback')
    return SpeechFrameDetector(SilenceTrimConfig())
