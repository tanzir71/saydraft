"""Opt-in, lossless local recordings for explicit History retries."""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

import numpy as np
import soundfile as sf


class AudioStore:
    def __init__(self, root, *, max_seconds=1200):
        self.root = Path(root).absolute()
        self.max_seconds = max_seconds

    def save(self, audio, sample_rate=16000):
        samples = np.asarray(audio, dtype=np.float32)
        if samples.ndim == 2 and samples.shape[1] == 1:
            samples = samples[:, 0]
        if samples.ndim != 1:
            raise ValueError("Retained recordings must be mono")
        if sample_rate != 16000 or len(samples) > sample_rate * self.max_seconds:
            raise ValueError("Recording exceeds the supported local retry format")
        if not np.isfinite(samples).all():
            raise ValueError("Recording contains invalid samples")
        self.root.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(self.root.resolve()).free < samples.nbytes + 16 * 1024 * 1024:
            raise OSError("Not enough disk space to retain the recording")
        final = self.root / (uuid.uuid4().hex + ".wav")
        partial = final.with_suffix(".wav.part")
        with partial.open("xb") as output:
            sf.write(output, samples, sample_rate, format="WAV", subtype="FLOAT")
            output.flush()
            os.fsync(output.fileno())
        partial.replace(final)
        return final

    def load(self, value):
        path = Path(value)
        # Reject external/UNC paths before resolve/stat can contact another host.
        if not path.is_absolute() or path.parent != self.root or path.suffix.lower() != ".wav":
            raise ValueError("Recording must belong to this local audio history")
        if path.is_symlink() or path.is_junction():
            raise ValueError("Linked recordings cannot be retried")
        resolved = path.resolve()
        if not resolved.is_relative_to(self.root.resolve()):
            raise ValueError("Recording escaped the audio history directory")
        info = sf.info(resolved)
        if info.samplerate != 16000 or info.channels != 1 or info.frames > 16000 * self.max_seconds:
            raise ValueError("Recording exceeds the supported local retry format")
        audio, rate = sf.read(resolved, dtype="float32")
        if not np.isfinite(audio).all():
            raise ValueError("Recording contains invalid samples")
        return audio, rate
