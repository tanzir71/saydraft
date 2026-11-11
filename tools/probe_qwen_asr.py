"""Developer-only Qwen ASR spike: pinned archive, offline CPU, retained reports.

Never downloads, opens a microphone or changes application model choices. Default
fixtures are an English smoke without a reference and one licensed Arabic clip.
An explicit private corpus can use the JSON format from tools.bench_models.
"""

import argparse
import hashlib
import json
import statistics
import tarfile
import threading
import time
from pathlib import Path

import numpy as np
import soundfile as sf

from saydraft.privacy.netguard import NetworkGuard
from saydraft.privacy.telemetry import disable_sherpa_telemetry
from tools.bench import current_rss_bytes
from tools.bench_languages import script_ratio
from tools.bench_models import score

ASSET_ID = 390698077
ARCHIVE_SHA256 = "393f8a14e2f5fb96746aaab342997a40641001fbd5bf9592a080a8329178ee96"
PREFIX = "sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25"
FILES = ("conv_frontend.onnx", "encoder.int8.onnx", "decoder.int8.onnx", "README.md",
         "tokenizer/vocab.json", "tokenizer/merges.txt", "tokenizer/tokenizer_config.json")


def extract_package(archive, directory):
    with archive.open("rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != ARCHIVE_SHA256:
            raise ValueError("Archive differs from the pinned Qwen asset")
    directory.mkdir(parents=True, exist_ok=False)
    wanted = {f"{PREFIX}/{name}": name for name in FILES}
    files = []
    with tarfile.open(archive, mode="r|bz2") as package:
        for member in package:
            name = wanted.get(member.name)
            if name is None:
                continue
            if not member.isfile() or not 0 < member.size <= 1024**3:
                raise ValueError("Unexpected Qwen package entry")
            destination = directory / name  # Constants only; never an archive-supplied destination.
            destination.parent.mkdir(parents=True, exist_ok=True)
            digest, size = hashlib.sha256(), 0
            with package.extractfile(member) as source, destination.open("xb") as output:
                while chunk := source.read(1024 * 1024):
                    size += len(chunk)
                    if size > member.size:
                        raise ValueError("Package payload exceeds its declared size")
                    digest.update(chunk)
                    output.write(chunk)
            if size != member.size:
                raise ValueError("Incomplete Qwen payload")
            files.append({"path": name, "size": size, "sha256": digest.hexdigest()})
            print("Verified extracted payload:", name, size, "bytes", flush=True)
    if {file["path"] for file in files} != set(FILES):
        raise ValueError("Qwen package lacks a required file")
    receipt = {"source_asset_id": ASSET_ID, "archive_sha256": ARCHIVE_SHA256, "files": files}
    (directory / "probe-receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return receipt


def run_probe(directory, receipt, *, corpus=None, iterations=3):
    import sherpa_onnx

    disable_sherpa_telemetry(sherpa_onnx)
    base = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
    if corpus is None:
        reference = json.loads((base / "fleurs-ar.json").read_text(encoding="utf-8"))
        clips = [{"audio": "hello.wav", "language": "en"},
                 {"audio": "fleurs-ar.wav", "language": "ar", "text": reference["reference"]}]
    else:
        base = corpus.resolve().parent
        clips = json.loads(corpus.read_text(encoding="utf-8"))["clips"]
        if not clips or any(not clip.get("text", "").strip() for clip in clips):
            raise ValueError("Private evaluation clips require independent reference transcripts")
    before_rss = current_rss_bytes()
    sampled_rss = [before_rss] if before_rss is not None else []
    stop = threading.Event()

    def sample():
        while not stop.wait(0.1):
            value = current_rss_bytes()
            if value is not None:
                sampled_rss.append(value)

    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    try:
        started = time.perf_counter()
        engine = sherpa_onnx.OfflineRecognizer.from_qwen3_asr(
            conv_frontend=str(directory / "conv_frontend.onnx"), encoder=str(directory / "encoder.int8.onnx"),
            decoder=str(directory / "decoder.int8.onnx"), tokenizer=str(directory / "tokenizer"),
            num_threads=4, provider="cpu", max_new_tokens=128, max_total_len=512)
        load_seconds, loaded_rss = time.perf_counter() - started, current_rss_bytes()

        def decode(audio, rate):
            stream = engine.create_stream()
            stream.accept_waveform(rate, audio)
            engine.decode_stream(stream)
            return stream.result.text.strip()

        rows = []
        for clip in clips:
            audio, rate = sf.read(base / clip["audio"], dtype="float32")
            if rate != 16000 or audio.ndim != 1:
                raise ValueError("Spike fixtures must be mono 16 kHz")
            decode(audio, rate)  # Warmup is excluded from the three timed runs.
            texts, seconds = [], []
            for _ in range(iterations):
                started = time.perf_counter()
                texts.append(decode(audio, rate))
                seconds.append(time.perf_counter() - started)
            metrics = score(clip["text"], texts[0]) if "text" in clip else None
            rows.append({"audio": clip["audio"], "language": clip.get("language"), "audio_seconds": len(audio) / rate,
                "text": texts[0], "stable_output": len(set(texts)) == 1, "transcribe_seconds": seconds,
                "median_seconds": statistics.median(seconds), "reference_available": metrics is not None,
                "wer": metrics["word_errors"] / max(1, metrics["reference_words"]) if metrics else None,
                "cer": metrics["character_errors"] / max(1, metrics["reference_characters"]) if metrics else None,
                "scores": metrics, "arabic_script_ratio": script_ratio(texts[0], "ARABIC") if clip.get("language") == "ar" else None})
            print("Completed", clip["audio"], "median seconds:", round(statistics.median(seconds), 3), flush=True)
        silence = decode(np.zeros(16000 * 3, dtype=np.float32), 16000)
        return {"offline": True, "scope": "reference_corpus" if corpus else "two_clip_smoke_only",
            "owner_accuracy_deferred": True, "runtime": sherpa_onnx.__version__, "provider": "cpu", "threads": 4,
            "generation_limits": {"max_new_tokens": 128, "max_total_len": 512},
            "source": receipt, "native_load_seconds": load_seconds, "rss_before_bytes": before_rss,
            "rss_loaded_bytes": loaded_rss, "sampled_peak_rss_bytes": max(sampled_rss, default=None),
            "rss_sampling_seconds": 0.1, "clips": rows, "silence_text": silence,
            "ship_decision": "none; evaluation only"}
    finally:
        stop.set()
        sampler.join()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("archive", "model-dir", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--corpus", type=Path)
    parser.add_argument("--iterations", type=int, default=3)
    args = parser.parse_args(argv)
    if args.model_dir.exists() or args.output.exists() or args.iterations < 1:
        parser.error("choose new model/report paths and a positive iteration count")
    NetworkGuard.install()
    try:
        receipt = extract_package(args.archive, args.model_dir)
        report = run_probe(args.model_dir, receipt, corpus=args.corpus, iterations=args.iterations)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as output:
            json.dump(report, output, ensure_ascii=False, indent=2)
        print(json.dumps({key: report[key] for key in ("scope", "runtime", "native_load_seconds", "sampled_peak_rss_bytes", "ship_decision")}))
    finally:
        NetworkGuard.uninstall()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
