"""Feed bundled audio in real time through preview and final ASR concurrently.

Uses only explicitly supplied installed model directories; no microphone or
downloads. Callback cadence and actual text changes are reported separately.
"""

import argparse
import json
import time
import threading
from pathlib import Path

import numpy as np
import soundfile as sf

from saydraft.asr.language_id import AudioLanguageIdentifier
from saydraft.asr.router import AsrRouter
from saydraft.asr.sherpa_parakeet import ParakeetEngine
from saydraft.asr.sherpa_stream import NemotronPreviewModel
from saydraft.config import default_config
from saydraft.core.preview import PreviewSession
from saydraft.core.segments import SegmentTranscriber
from saydraft.models.benchmark import fixture_path
from saydraft.privacy.netguard import NetworkGuard


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview-dir", type=Path, required=True)
    parser.add_argument("--parakeet-dir", type=Path, required=True)
    parser.add_argument("--lid-dir", type=Path)
    parser.add_argument("--seconds", type=int, default=8)
    parser.add_argument("--streaming-result", action="store_true", help="Flush preview instead of discarding at release")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists() or not 8 <= args.seconds <= 120:
        parser.error("choose a new report path and a duration from 8 to 120 seconds")
    NetworkGuard.install()
    preview = background = None
    preview_started = background_started = False
    try:
        primary = ParakeetEngine(model_dir=args.parakeet_dir)
        if args.lid_dir:
            primary = AsrRouter(default_config(), engine_factory=lambda config, route, base=primary: base,
                installed=lambda model: False, language_identifier=AudioLanguageIdentifier(model_dir=args.lid_dir))
        preview_model = NemotronPreviewModel(model_dir=args.preview_dir)
        primary.prepare()
        preview_model.prepare()
        clip, rate = sf.read(fixture_path(), dtype="float32")
        assert rate == 16000
        audio = np.tile(clip, (args.seconds + 7) // 8)[:args.seconds * rate]
        callbacks, changed, failures = [], [], []
        previous = [""]
        capturing = threading.Event()
        started = time.perf_counter()

        def on_partial(text):
            if capturing.is_set():
                elapsed = time.perf_counter() - started
                callbacks.append(elapsed)
                if text != previous[0]:
                    changed.append(elapsed)
                    previous[0] = text

        preview = PreviewSession(preview_model, on_partial=on_partial, on_failed=lambda: failures.append(True))
        background = SegmentTranscriber(primary)
        preview_started = preview.start()
        assert preview_started
        background.start()
        background_started = True
        started = time.perf_counter()
        capturing.set()
        for offset in range(0, len(audio), 1600):
            frame = audio[offset:offset + 1600]
            background.feed(frame)
            preview.feed(frame)
            remaining = started + (offset + len(frame)) / rate - time.perf_counter()
            if remaining > 0:
                time.sleep(remaining)
        capturing.clear()
        feed_seconds = time.perf_counter() - started
        released = time.perf_counter()
        preview.request_finish(discard=not args.streaming_result)
        primary_result = background.finish()
        preview_result = preview.finish()
        release_seconds = time.perf_counter() - released
        counts = [sum(second <= value < second + 1 for value in callbacks) for second in range(args.seconds)]
        report = {"offline": True, "scope": "repeated fixture, CPU four threads per recognizer; no accuracy claim",
                  "fixture_seconds": args.seconds, "feed_seconds": feed_seconds,
                  "preview_callbacks": len(callbacks), "preview_callbacks_per_second": len(callbacks) / feed_seconds,
                  "minimum_steady_callbacks_per_second": min(counts[1:-1]), "callbacks_per_second": counts,
                  "actual_text_changes": len(changed), "preview_failed": preview_result.failed,
                  "preview_failure_reason": preview_result.failure_reason,
                  "preview_complete": preview_result.complete, "streaming_result_requested": args.streaming_result,
                  "preview_compute_seconds": preview_result.compute_seconds, "primary_failed": primary_result.failed,
                  "primary_segments": primary_result.segments, "primary_nonempty": bool(primary_result.text),
                  "release_seconds": release_seconds, "failure_notifications": len(failures)}
        report["passed"] = bool(report["minimum_steady_callbacks_per_second"] >= 4 and
                                not report["preview_failed"] and not report["primary_failed"] and
                                report["primary_nonempty"] and (not args.streaming_result or preview_result.complete))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
        print(json.dumps(report))
        return 0 if report["passed"] else 1
    finally:
        if preview_started:
            preview.request_finish(discard=True)
        if background_started:
            background.finish(discard=True)
        if preview_started:
            preview.finish(discard=True)
        NetworkGuard.uninstall()


if __name__ == "__main__":
    raise SystemExit(main())
