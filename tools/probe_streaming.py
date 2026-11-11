"""Probe the pinned 160 ms Nemotron archive offline before enabling a Labs feature.

This developer tool never downloads. It verifies the archive, extracts only the
named regular files into a new directory, and benchmarks real-time decode/result
callbacks separately from actual text changes. It never opens a microphone.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import tarfile
import time
from pathlib import Path

import numpy as np
import soundfile as sf

from saydraft.models.benchmark import fixture_path
from saydraft.privacy.netguard import NetworkGuard
from saydraft.privacy.telemetry import disable_sherpa_telemetry

ARCHIVE_SHA256 = "0ae73a41cd51599dc7cac9ac083d9d35de53d762ca45923505fde47a3751814b"
ASSET_ID = 405279013
PREFIX = "sherpa-onnx-nemotron-speech-streaming-en-0.6b-160ms-int8-2026-04-25"
FILES = ("encoder.int8.onnx", "decoder.int8.onnx", "joiner.int8.onnx", "tokens.txt", "README.md")


def extract_package(archive, directory):
    with archive.open("rb") as handle:
        if hashlib.file_digest(handle, "sha256").hexdigest() != ARCHIVE_SHA256:
            raise ValueError("Archive differs from the pinned GitHub asset")
    directory.mkdir(parents=True, exist_ok=False)
    wanted = {f"{PREFIX}/{name}": name for name in FILES}
    files = []
    with tarfile.open(archive, mode="r|bz2") as package:
        for member in package:
            name = wanted.get(member.name)
            if name is None:
                continue  # Unlisted files, paths and links are never written.
            if not member.isfile() or not 0 < member.size <= 800 * 1024**2:
                raise ValueError("Unexpected package entry")
            destination = directory / name  # All destination names are constants above.
            digest, size = hashlib.sha256(), 0
            with package.extractfile(member) as source, destination.open("xb") as output:
                while chunk := source.read(1024 * 1024):
                    size += len(chunk)
                    if size > member.size:
                        raise ValueError("Package entry exceeds its declared size")
                    digest.update(chunk)
                    output.write(chunk)
            if size != member.size:
                raise ValueError("Package entry is incomplete")
            files.append({"path": name, "size": size, "sha256": digest.hexdigest()})
    if {item["path"] for item in files} != set(FILES):
        raise ValueError("Package lacks a required model file")
    receipt = {"archive_sha256": ARCHIVE_SHA256, "source_asset_id": ASSET_ID, "files": files}
    (directory / "probe-receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return receipt


def run_probe(directory, receipt):
    import sherpa_onnx

    disable_sherpa_telemetry(sherpa_onnx)
    started = time.perf_counter()
    engine = sherpa_onnx.OnlineRecognizer.from_transducer(
        encoder=str(directory / "encoder.int8.onnx"), decoder=str(directory / "decoder.int8.onnx"),
        joiner=str(directory / "joiner.int8.onnx"), tokens=str(directory / "tokens.txt"),
        num_threads=4, provider="cpu", decoding_method="greedy_search", enable_endpoint_detection=False)
    load_seconds = time.perf_counter() - started
    audio, rate = sf.read(fixture_path(), dtype="float32")
    assert rate == 16000
    stream = engine.create_stream()
    callbacks, costs, changed = [], [], []
    previous = ""
    started = time.perf_counter()
    for offset in range(0, len(audio), 2560):  # Real-time 160 ms feed.
        engine_started = time.perf_counter()
        stream.accept_waveform(16000, audio[offset:offset + 2560])
        while engine.is_ready(stream):
            engine.decode_stream(stream)
            text = engine.get_result(stream)
            elapsed = time.perf_counter() - started
            callbacks.append(elapsed)
            if text != previous:
                changed.append(elapsed)
                previous = text
        costs.append(time.perf_counter() - engine_started)
        remaining = started + min(offset + 2560, len(audio)) / rate - time.perf_counter()
        if remaining > 0:
            time.sleep(remaining)
    feed_seconds = time.perf_counter() - started
    tail_started = time.perf_counter()
    stream.accept_waveform(16000, np.zeros(int(0.66 * rate), dtype=np.float32))
    stream.input_finished()
    while engine.is_ready(stream):
        engine.decode_stream(stream)
    text = engine.get_result(stream)
    counts = [sum(second <= item < second + 1 for item in callbacks) for second in range(8)]
    intervals = np.diff(callbacks)
    min_steady = min(counts[1:-1])
    return {"offline": True, "scope": "repeated eight-second fixture, CPU four threads; no accuracy claim",
            "source": receipt, "runtime": sherpa_onnx.__version__, "native_load_seconds": load_seconds,
            "feed_seconds": feed_seconds, "callback_count": len(callbacks), "callbacks_per_second": len(callbacks) / feed_seconds,
            "cadence_scope": "decode/result callbacks; text may be unchanged",
            "callbacks_per_audio_second": counts, "minimum_steady_callbacks_per_second": min_steady,
            "changed_text_count": len(changed), "text_changes_per_second": len(changed) / feed_seconds,
            "callback_interval_p95_seconds": float(np.percentile(intervals, 95)) if len(intervals) else None,
            "feed_step_p50_seconds": statistics.median(costs), "feed_step_max_seconds": max(costs),
            "finalize_seconds": time.perf_counter() - tail_started, "final_text": text,
            "passed": bool(text.strip() and min_steady >= 4 and len(callbacks) / feed_seconds >= 4)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True, help="A new directory; existing files are retained")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.model_dir.exists() or args.output.exists():
        parser.error("choose new model/report paths; existing files are retained")
    NetworkGuard.install()
    try:
        receipt = extract_package(args.archive, args.model_dir)
        report = run_probe(args.model_dir, receipt)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
        print(json.dumps({key: value for key, value in report.items() if key not in ("source", "final_text")}))
        return 0 if report["passed"] else 1
    finally:
        NetworkGuard.uninstall()


if __name__ == "__main__":
    raise SystemExit(main())
