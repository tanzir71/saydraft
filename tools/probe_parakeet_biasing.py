"""Offline API/latency smoke for Parakeet hotwords, not a dictionary accuracy test.

With a supplied BPE vocabulary, hotwords come from baseline output solely to
test the native API, never to calculate accuracy gains. The pinned conversion
does not include that vocabulary; without one, only decoding is compared.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from pathlib import Path

import numpy as np
import soundfile as sf

from saydraft.asr.model_ids import DEFAULT_MODEL
from saydraft.models.downloader import installation_ready
from saydraft.models.manifest import get_model
from saydraft.privacy.netguard import NetworkGuard
from saydraft.privacy.telemetry import disable_sherpa_telemetry


def probe(directory, iterations, bpe_vocab=None):
    import sherpa_onnx

    if not installation_ready(get_model(DEFAULT_MODEL), directory, check_hashes=True):
        raise ValueError("Provide a complete verified Parakeet v3 directory")
    disable_sherpa_telemetry(sherpa_onnx)
    audio, rate = sf.read(Path(__file__).resolve().parents[1] / "tests/fixtures/hello.wav", dtype="float32")
    assert rate == 16000
    hotwords = ""
    rows = []
    for method in ("greedy_search", "modified_beam_search"):
        started = time.perf_counter()
        engine = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(directory / "encoder.int8.onnx"), decoder=str(directory / "decoder.int8.onnx"),
            joiner=str(directory / "joiner.int8.onnx"), tokens=str(directory / "tokens.txt"),
            model_type="nemo_transducer", num_threads=4, provider="cpu",
            decoding_method=method, max_active_paths=4, hotwords_score=1.5,
            modeling_unit="bpe" if bpe_vocab else "cjkchar", bpe_vocab=str(bpe_vocab or ""))
        loaded = time.perf_counter() - started
        for use_hotwords in ((False, True) if method != "greedy_search" and bpe_vocab else (False,)):
            costs, texts = [], []
            for _ in range(iterations):
                started = time.perf_counter()
                stream = engine.create_stream(hotwords) if use_hotwords else engine.create_stream()
                stream.accept_waveform(16000, audio)
                engine.decode_stream(stream)
                costs.append(time.perf_counter() - started)
                texts.append(stream.result.text)
                if method == "greedy_search":
                    hotwords = stream.result.text
            silence = engine.create_stream(hotwords) if use_hotwords else engine.create_stream()
            silence.accept_waveform(16000, np.zeros(48000, dtype=np.float32))
            engine.decode_stream(silence)
            rows.append({"method": method, "hotwords": use_hotwords, "native_load_seconds": loaded,
                         "iterations": iterations, "recognition_p50_seconds": statistics.median(costs),
                         "nonempty": sum(bool(text.strip()) for text in texts), "texts": texts,
                         "silence_nonempty": bool(silence.result.text.strip()), "silence_text": silence.result.text})
    return {"offline": True, "model": DEFAULT_MODEL, "runtime": sherpa_onnx.__version__,
            "scope": "bundled fixture API/latency smoke only", "accuracy_evaluated": False,
            "hotword_source": "self-seeded greedy text, never a reference" if bpe_vocab else None,
            "bpe_vocab_sha256": hashlib.sha256(bpe_vocab.read_bytes()).hexdigest() if bpe_vocab else None,
            "hotwords_evaluated": bpe_vocab is not None, "rows": rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--bpe-vocab", type=Path, help="Optional matching local vocabulary, not downloaded")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists() or args.iterations < 1:
        parser.error("choose a new output path and a positive iteration count")
    if args.bpe_vocab and not args.bpe_vocab.is_file():
        parser.error("provide an existing local BPE vocabulary")
    NetworkGuard.install()
    try:
        report = probe(args.model_dir, args.iterations, args.bpe_vocab)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
        print(json.dumps({"scope": report["scope"], "rows": [
            {key: value for key, value in row.items() if key not in ("texts", "silence_text")}
            for row in report["rows"]]}))
    finally:
        NetworkGuard.uninstall()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
