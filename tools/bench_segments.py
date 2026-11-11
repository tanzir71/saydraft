"""Feed a 60-second repeated speech fixture in real time; no microphone or network.

This is a latency check, not an accuracy corpus. Only cached models are allowed.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import soundfile as sf

from saydraft.audio.vad import trim_silence
from saydraft.core.segments import SegmentTranscriber
from saydraft.privacy.netguard import NetworkGuard
from saydraft.stt.whisper_engine import WhisperEngine, WhisperEngineConfig


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="base")
    parser.add_argument("--parakeet-dir", type=Path, help="Use verified Parakeet v3 instead of cached Whisper")
    parser.add_argument("--continuous", action="store_true",
                        help="Force speech detection throughout the repeated clip to exercise the segment cap")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("choose a new output file; existing reports are preserved")
    NetworkGuard.install()
    audio, rate = sf.read(Path(__file__).resolve().parents[1] / "tests/fixtures/hello.wav", dtype="float32")
    assert rate == 16000 and len(audio) == 48000
    block = np.concatenate((audio, np.zeros(16000, dtype=np.float32)))
    spoken_tail = trim_silence(audio)
    tail = np.concatenate((np.zeros(64000 - len(spoken_tail), dtype=np.float32), spoken_tail))
    fixture = np.concatenate([block] * 14 + [tail])
    if args.continuous:
        fixture = np.tile(audio, 20)
    assert len(fixture) == 60 * rate
    if args.parakeet_dir:
        from saydraft.asr.sherpa_parakeet import ParakeetEngine

        engine = ParakeetEngine(model_dir=args.parakeet_dir)
        engine.prepare()
        model_id = engine.model_id
    else:
        engine = WhisperEngine(WhisperEngineConfig(model_size=args.model, language="en", local_files_only=True))
        engine._load_model()
        model_id = args.model

    class MeasuredEngine:
        last_audio = None
        last_seconds = None

        def __init__(self):
            self.segment_lengths = []

        def transcribe(self, segment):
            self.last_audio = segment.copy()
            self.segment_lengths.append(len(segment))
            started = time.perf_counter()
            text = engine.transcribe(segment)
            self.last_seconds = time.perf_counter() - started
            return text

    measured = MeasuredEngine()
    background = SegmentTranscriber(measured, detector=(lambda frame: True) if args.continuous else None)
    background.start()
    started = time.perf_counter()
    for offset in range(0, len(fixture), 1600):
        background.feed(fixture[offset:offset + 1600])
        remaining = started + (offset + 1600) / rate - time.perf_counter()
        if remaining > 0:
            time.sleep(remaining)
    committed_before_release = background.completed_segments
    released_at = time.perf_counter()
    result = background.finish()
    release_seconds = time.perf_counter() - released_at
    if measured.last_audio is None:
        raise RuntimeError("fixture produced no speech segments")
    reference_started = time.perf_counter()
    engine.transcribe(measured.last_audio)
    reference_seconds = time.perf_counter() - reference_started
    report = {
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(), "processor": platform.processor(), "logical_cpus": os.cpu_count(),
        "model": model_id, "fixture_seconds": 60, "realtime_feed": True,
        "forced_continuous_segmentation": args.continuous,
        "maximum_segment_seconds": max(measured.segment_lengths) / rate,
        "segments_before_release": committed_before_release, "total_segments": result.segments,
        "release_to_raw_seconds": release_seconds, "last_segment_seconds": len(measured.last_audio) / rate,
        "reference_last_segment_asr_seconds": reference_seconds,
        "budget_seconds": 1.3 * reference_seconds, "background_failed": result.failed,
        "passed": bool(result.text and not result.failed and release_seconds <= 1.3 * reference_seconds
                       and max(measured.segment_lengths) <= 25 * rate),
        "scope": "repeated bundled fixture, warm cached ASR; no microphone, insertion or accuracy claim",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
