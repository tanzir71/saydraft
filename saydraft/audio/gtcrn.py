"""Verified local GTCRN inference with bounded windows and complete sample coverage."""

from pathlib import Path

import numpy as np

MODEL_ID = 'gtcrn-speech-enhancement'


def _create_denoiser(path):
    import sherpa_onnx
    from saydraft.privacy.telemetry import disable_sherpa_telemetry
    disable_sherpa_telemetry(sherpa_onnx)
    config = sherpa_onnx.OfflineSpeechDenoiserConfig(
        model=sherpa_onnx.OfflineSpeechDenoiserModelConfig(
            gtcrn=sherpa_onnx.OfflineSpeechDenoiserGtcrnModelConfig(model=str(path)),
            num_threads=1, provider='cpu', debug=False))
    if not config.validate():
        raise ValueError('Whisper-mode enhancement configuration is unavailable')
    return sherpa_onnx.OfflineSpeechDenoiser(config)


class GtcrnDenoiser:
    def __init__(self, directory=None, *, factory=_create_denoiser):
        from saydraft.models.downloader import installation_ready
        from saydraft.models.manifest import get_model
        if directory is None:
            from saydraft.model_download import find_installed_model
            directory = find_installed_model(MODEL_ID, check_hashes=True)
        self.directory = Path(directory) if directory is not None else None
        self._descriptor = get_model(MODEL_ID)
        if self.directory is None or not installation_ready(self._descriptor, self.directory, check_hashes=True):
            raise FileNotFoundError('Set up speech enhancement in Settings > Microphone, or turn enhancement off')
        self._engine = factory(self.directory / 'gtcrn_simple.onnx')

    def __call__(self, audio):
        from saydraft.models.downloader import installation_ready
        if not installation_ready(self._descriptor, self.directory, check_hashes=True):
            raise ValueError('Speech enhancement files changed; review setup in Settings > Microphone')
        waveform = np.asarray(audio, dtype=np.float32)
        if waveform.ndim != 1 or not np.isfinite(waveform).all():
            raise ValueError('Speech enhancement requires finite mono 16 kHz audio')
        if not len(waveform):
            return waveform.copy()
        result = np.empty_like(waveform)
        # Limit native STFT allocations; one second of prefix warms recurrent
        # context, and lookahead keeps segment edges out of the retained window.
        for start in range(0, len(waveform), 400_000):
            end = min(len(waveform), start + 400_000)
            first, last = max(0, start - 16_000), min(len(waveform), end + 512)
            part = waveform[first:last]
            # The pinned runtime rounds output down to a 256-sample hop. Pad
            # before inference; only discard padding, never original samples.
            padded_size = max(512, ((len(part) + 255) // 256) * 256)
            padded = np.pad(part, (0, padded_size - len(part)))
            output = self._engine(np.ascontiguousarray(padded), 16000)
            samples = np.asarray(output.samples, dtype=np.float32)
            offset, count = start - first, end - start
            if output.sample_rate != 16000 or samples.ndim != 1 or len(samples) < offset + count:
                raise ValueError('Speech enhancement returned incomplete audio')
            kept = samples[offset:offset + count]
            if not np.isfinite(kept).all():
                raise ValueError('Speech enhancement returned invalid audio')
            result[start:end] = kept
        return result
