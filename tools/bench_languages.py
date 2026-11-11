"""Run the bundled Bengali/Arabic smoke clips with a verified local Whisper turbo.

This checks transcription script, not recognition accuracy. It never downloads.
"""

from __future__ import annotations

import argparse
import json
import platform
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import soundfile as sf

from saydraft.asr.whisper_ct2 import TURBO_MODEL, WhisperCT2Engine, WhisperEngineConfig
from saydraft.models.downloader import installation_ready
from saydraft.models.manifest import get_model
from saydraft.privacy.netguard import NetworkGuard
from saydraft.stt.whisper_engine import _import_whisper_model


def script_ratio(text, script):
    letters = [char for char in text if char.isalpha()]
    matching = sum(unicodedata.name(char, "").startswith(script) for char in letters)
    return matching / max(1, len(letters))


def run_smoke(directory):
    model_info = get_model("whisper-" + TURBO_MODEL)
    if not installation_ready(model_info, directory, check_hashes=True):
        raise ValueError("Provide a complete, SHA-256 verified Whisper turbo directory")
    NetworkGuard.install()
    try:
        started = time.perf_counter()
        model_class = _import_whisper_model(suppress_ipv6_probe=True)
        model = model_class(str(directory), device="cpu", compute_type="int8", local_files_only=True)
        load_seconds = time.perf_counter() - started
        rows = []
        root = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
        for language, script in (("bn", "BENGALI"), ("ar", "ARABIC")):
            engine = WhisperCT2Engine(WhisperEngineConfig(model_size=TURBO_MODEL, language=language),
                                      model_factory=lambda *args, **kwargs: model)
            engine.prepare()
            audio, rate = sf.read(root / f"fleurs-{language}.wav", dtype="float32")
            if rate != 16000:
                raise ValueError("smoke fixtures must be 16 kHz")
            started = time.perf_counter()
            text = engine.transcribe(audio)
            ratio = script_ratio(text, script)
            rows.append({"language": language, "audio_seconds": len(audio) / rate,
                         "text": text, "script_ratio": ratio,
                         "transcribe_seconds": time.perf_counter() - started,
                         "passed": len([char for char in text if char.isalpha()]) >= 8 and ratio >= 0.9})
        return {"measured_at": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
                "model": model_info["id"], "revision": model_info["revision"], "compute_type": "int8",
                "native_load_seconds": load_seconds, "offline": True, "scope": "script_smoke_only",
                "clips": rows, "passed": all(row["passed"] for row in rows)}
    finally:
        NetworkGuard.uninstall()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("choose a new output file; existing reports are retained")
    report = run_smoke(args.model_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(report, output, indent=2, ensure_ascii=False)
    print(json.dumps({"passed": report["passed"], "clips": [
        {key: row[key] for key in ("language", "script_ratio", "transcribe_seconds", "passed")}
        for row in report["clips"]]}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
