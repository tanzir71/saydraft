"""Verified local speaker turns; one call gives consistent cluster IDs within it.

Run on an analysis worker, after native capture has stopped. The pinned sherpa
callback reports progress but cannot interrupt native processing. Cancellation
therefore discards a finished native result; it does not claim an immediate exit.
Speaker numbers are acoustic clusters, not identified people or assigned names.
"""

from dataclasses import dataclass
import math
from pathlib import Path
import threading

import numpy as np

from saydraft.models.downloader import installation_ready
from saydraft.models.manifest import get_model
from .audio import SAMPLE_RATE
from .limits import MAX_ANALYSIS_SAMPLES
from .models import EMBEDDING_MODEL, SEGMENTATION_MODEL


class DiarizationCancelled(Exception):
    pass


@dataclass(frozen=True)
class SpeakerTurn:
    start: float
    end: float
    speaker: int


def _create_diarizer(segmentation, embedding, *, threads, num_speakers, threshold):
    import sherpa_onnx as sherpa
    from saydraft.privacy.telemetry import disable_sherpa_telemetry

    disable_sherpa_telemetry(sherpa)
    config = sherpa.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa.OfflineSpeakerSegmentationPyannoteModelConfig(model=str(segmentation)),
            num_threads=threads, provider='cpu', debug=False),
        embedding=sherpa.SpeakerEmbeddingExtractorConfig(model=str(embedding), num_threads=threads,
                                                       provider='cpu', debug=False),
        clustering=sherpa.FastClusteringConfig(num_clusters=num_speakers, threshold=threshold),
        min_duration_on=.3, min_duration_off=.5)
    if not config.validate():
        raise ValueError('The installed meeting speaker models are incompatible')
    return sherpa.OfflineSpeakerDiarization(config)


class SpeakerDiarizer:
    def __init__(self, *, resolver=None, factory=_create_diarizer, threads=2,
                 num_speakers=-1, threshold=.5):
        if (type(threads) is not int or not 1 <= threads <= 8 or type(num_speakers) is not int
                or num_speakers != -1 and not 1 <= num_speakers <= 32
                or type(threshold) not in (int, float) or not math.isfinite(threshold) or not 0 < threshold <= 1):
            raise ValueError('Invalid meeting speaker settings')
        self._resolver, self._factory = resolver, factory
        self._threads, self._num_speakers, self._threshold = threads, num_speakers, float(threshold)
        self._native, self._lock = None, threading.RLock()

    def prepare(self):
        with self._lock:
            if self._native is not None:
                return
            resolver = self._resolver
            if resolver is None:
                from saydraft.model_download import find_installed_model
                resolver = find_installed_model
            paths = []
            for model_id, payload in ((SEGMENTATION_MODEL, 'model.onnx'), (EMBEDDING_MODEL, 'embedding.onnx')):
                directory = resolver(model_id, check_hashes=True)
                if directory is None or not installation_ready(get_model(model_id), Path(directory), check_hashes=True):
                    raise FileNotFoundError('Review and download both meeting speaker models in setup first')
                paths.append((Path(directory) / payload).resolve())
            native = self._factory(*paths, threads=self._threads, num_speakers=self._num_speakers,
                                   threshold=self._threshold)
            if native.sample_rate != SAMPLE_RATE:
                raise ValueError('Meeting speaker models require mono 16 kHz audio')
            self._native = native

    def diarize(self, audio, *, cancelled=lambda: False, on_progress=None):
        """Analyze a complete meeting timeline; overlapping speaker turns remain separate."""
        if not callable(cancelled) or on_progress is not None and not callable(on_progress):
            raise ValueError('Invalid meeting analysis callbacks')
        waveform = np.asarray(audio)
        if (waveform.ndim != 1 or waveform.dtype.kind != 'f'
                or len(waveform) > MAX_ANALYSIS_SAMPLES
                or not np.isfinite(waveform).all() or np.any(np.abs(waveform) > 8)):
            raise ValueError('Invalid meeting speaker audio')
        if cancelled():
            raise DiarizationCancelled()
        if not len(waveform):
            return ()
        waveform = np.ascontiguousarray(waveform, dtype=np.float32)
        with self._lock:
            self.prepare()
            if cancelled():
                raise DiarizationCancelled()
            callback_failure = []
            def progress(done, total):
                if on_progress is not None and not callback_failure:
                    try:
                        on_progress(max(0.0, min(1.0, done / max(1, total))))
                    except Exception as error:
                        callback_failure.append(error)
                return 0  # The pinned runtime ignores this value; it is not cancellation.
            result = self._native.process(waveform, callback=progress).sort_by_start_time()
            if cancelled():
                raise DiarizationCancelled()
            if callback_failure:
                raise RuntimeError('Meeting progress consumer failed') from callback_failure[0]
            if len(result) > 100_000:
                raise ValueError('Meeting speaker output exceeds its bound')
            duration, turns = len(waveform) / SAMPLE_RATE, []
            for item in result:
                start, end, speaker = item.start, item.end, item.speaker
                if (type(start) not in (int, float) or type(end) not in (int, float)
                        or not math.isfinite(start) or not math.isfinite(end) or not 0 <= start < end
                        or start >= duration or end > duration + .1
                        or type(speaker) is not int or not 0 <= speaker < 32):
                    raise ValueError('Invalid meeting speaker turn')
                turns.append(SpeakerTurn(float(start), min(duration, float(end)), speaker))
            return tuple(sorted(turns, key=lambda turn: (turn.start, turn.end, turn.speaker)))
