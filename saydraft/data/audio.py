"""Opt-in, lossless local recordings for explicit History retries."""

from __future__ import annotations

import os
import shutil
import uuid
import re
import stat
import threading
import weakref
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import soundfile as sf

_LOCKS = weakref.WeakValueDictionary()
_LOCKS_GUARD = threading.Lock()


def _shared_lock(root):
    with _LOCKS_GUARD:
        key = os.path.normcase(str(root))
        lock = _LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _LOCKS[key] = lock
        return lock


class AudioStore:
    def __init__(self, root, *, max_seconds=1200):
        self.root = Path(root).absolute()
        self.max_seconds = max_seconds
        self._lease = _shared_lock(self.root)

    @contextmanager
    def lease(self, _value):
        with self._lease:
            yield

    def expire(self, value, cutoff, *, clear_reference, cancelled=lambda:False):
        path = Path(value)
        if (not path.is_absolute() or path.parent!=self.root
                or not re.fullmatch(r"[0-9a-f]{32}\.wav",path.name)
                or str(self.root).startswith(("\\\\","//"))):
            return "skipped"
        if not self._lease.acquire(blocking=False):
            return "skipped"
        try:
            if cancelled():
                return "skipped"
            if self.root.is_symlink() or self.root.is_junction():
                return "skipped"
            root = self.root.resolve(strict=True)
            root_info = root.stat()
            target = root/path.name
            try:
                info = target.lstat()
            except FileNotFoundError:
                if cancelled():
                    return "skipped"
                clear_reference()
                return "unavailable"
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_mtime>=cutoff
                    or getattr(info,"st_file_attributes",0)&getattr(stat,"FILE_ATTRIBUTE_REPARSE_POINT",0)
                    or target.resolve().parent!=root):
                return "skipped"
            # Recheck the exact local directory/file identities immediately before
            # unlinking this single managed entry. Never traverse an audio link.
            current, parent = target.lstat(), root.stat()
            if (current.st_dev,current.st_ino,current.st_size,current.st_mtime_ns)!=(
                    info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns) or (
                    parent.st_dev,parent.st_ino)!=(root_info.st_dev,root_info.st_ino) or cancelled():
                return "skipped"
            target.unlink()
            try:
                clear_reference()
            except Exception:
                return "removed_unindexed"  # The next sweep repairs the stale reference.
            return "removed"
        finally:
            self._lease.release()

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
        with self._lease:
            return self._load(value)

    def _load(self, value):
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
