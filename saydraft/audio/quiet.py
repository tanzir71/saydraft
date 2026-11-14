"""Opt-in quiet-speech gain and AGC; capture buffers are never modified."""

from dataclasses import dataclass
import math

import numpy as np


@dataclass(frozen=True)
class QuietSpeechSettings:
    enabled: bool = False
    gain_db: float = 12.0
    agc: bool = True
    enhancement: bool = True

    def __post_init__(self):
        if (any(type(value) is not bool for value in (self.enabled, self.agc, self.enhancement))
                or type(self.gain_db) not in (int, float) or not math.isfinite(self.gain_db)
                or not 0 <= self.gain_db <= 24):
            raise ValueError("Choose a finite Whisper-mode gain between 0 and 24 dB")

    @classmethod
    def from_config(cls, config):
        options = config.get('recording', {})
        return cls(options.get('whisper_mode', False), options.get('whisper_gain_db', 12.0),
            options.get('whisper_agc', True), options.get('whisper_enhancement', True))


def vad_settings(config):
    """One profile for engine trimming and raw-audio background segmentation."""
    stt = config.get('stt', {})
    values = dict(silence_trim=stt.get('silence_trim', True),
        silence_padding_ms=stt.get('silence_padding_ms', 120),
        vad_aggressiveness=stt.get('vad_aggressiveness', 2),
        vad_energy_threshold=stt.get('vad_energy_threshold', 0.003), silero_threshold=0.5)
    if QuietSpeechSettings.from_config(config).enabled:
        values.update(silence_padding_ms=max(200, values['silence_padding_ms']),
            vad_aggressiveness=min(1, values['vad_aggressiveness']),
            vad_energy_threshold=min(0.00075, values['vad_energy_threshold']), silero_threshold=0.35)
    return values


def gain_and_agc(audio, settings):
    """20 ms gain ramps with a peak ceiling and no upward AGC on near-silence."""
    samples = np.asarray(audio, dtype=np.float32)
    if samples.ndim != 1 or not np.isfinite(samples).all():
        raise ValueError("Whisper mode requires finite mono 16 kHz audio")
    if not settings.enabled:
        return samples
    output = np.empty_like(samples)
    fixed = 10 ** (settings.gain_db / 20)
    previous = 1.0
    for start in range(0, len(samples), 320):
        raw = samples[start:start + 320]
        frame = raw * fixed
        peak = float(np.max(np.abs(frame))) if len(frame) else 0
        rms = float(np.sqrt(np.mean(np.square(raw, dtype=np.float64))))
        desired = min(8.0, 0.08 / max(rms * fixed, 1e-12)) if settings.agc else 1.0
        if rms < 0.0001:
            desired = min(desired, 1.0)  # Keep silence/noise from winding AGC up.
        ceiling = min(8.0, 0.98 / peak) if peak else 8.0
        desired = min(desired, ceiling)
        previous = min(previous, ceiling)
        seconds = len(frame) / 16000
        tau = 0.01 if desired < previous else 0.25
        end = previous + (desired - previous) * (1 - math.exp(-seconds / tau))
        ramp = np.linspace(previous, end, len(frame), dtype=np.float32)
        output[start:start + len(frame)] = frame * ramp
        previous = end
    if not np.isfinite(output).all():
        raise ValueError("Whisper-mode gain could not process this audio")
    return output


class QuietSpeechProcessor:
    def __init__(self, settings, *, denoiser_factory=None):
        self.settings = settings
        self._factory = denoiser_factory
        self._denoiser = None

    def prepare(self):
        if self.settings.enabled and self.settings.enhancement and self._denoiser is None:
            if self._factory is None:
                from .gtcrn import GtcrnDenoiser
                self._denoiser = GtcrnDenoiser()
            else:
                self._denoiser = self._factory()

    def process(self, audio):
        if not self.settings.enabled:
            return audio
        waveform = gain_and_agc(audio, self.settings)
        if not len(waveform):
            return waveform
        self.prepare()
        if self._denoiser is not None:
            enhanced = np.asarray(self._denoiser(waveform), dtype=np.float32)
            if enhanced.shape != waveform.shape or not np.isfinite(enhanced).all():
                raise ValueError("Whisper-mode enhancement did not preserve the recording")
            # Denoising may create peaks; a uniform scale avoids hard clipping.
            peak = float(np.max(np.abs(enhanced)))
            waveform = enhanced * min(1.0, 0.98 / peak) if peak else enhanced
        return np.ascontiguousarray(waveform, dtype=np.float32)

    def close(self):
        self._denoiser = None
