"""Cross-check committed cues with FFmpeg's loudness/true-peak meter, never playback."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def verify(output: Path, ffmpeg: str):
    root = ROOT / "saydraft/ui/sound_assets"
    manifest = json.loads((root / "manifest.json").read_text("utf-8"))
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for name in ("start", "end", "command"):
        entry = manifest["cues"][name]
        path = root / entry["file"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == entry["sha256"]
        result = subprocess.run([ffmpeg, "-hide_banner", "-nostdin", "-i", str(path), "-af",
            "apad=whole_dur=0.4,ebur128=peak=true", "-f", "null", "-"],
            capture_output=True, text=True, check=True)
        (output / f"{name}-meter.log").write_text(result.stderr, encoding="utf-8")
        summary = result.stderr.rsplit("Summary:", 1)[1]
        loudness = float(re.search(r"I:\s*(-?[\d.]+)\s*LUFS", summary)[1])
        peak = float(re.search(r"Peak:\s*(-?[\d.]+)\s*dBFS", summary)[1])
        assert abs(loudness - entry["target_lufs"]) <= .1, (name, loudness)
        assert peak <= -1, (name, peak)
        rows.append({"cue": name, "sha256": digest, "duration_ms": entry["duration_ms"],
            "integrated_lufs_400ms_padded": loudness, "true_peak_dbfs": peak})
    report = {"source_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()),
        "ffmpeg": subprocess.check_output([ffmpeg, "-version"], text=True).splitlines()[0],
        "measurement": "Cue followed by silence to complete one 400 ms BS.1770 block; padding is not in the WAV",
        "audio_device_opened": False, "playback_performed": False, "cues": rows}
    (output / "sounds.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="New directory for meter reports")
    parser.add_argument("--ffmpeg", default=shutil.which("ffmpeg"), help="FFmpeg executable (only a meter is run)")
    args = parser.parse_args()
    if not args.ffmpeg:
        parser.error("Provide --ffmpeg or put FFmpeg on PATH")
    report = verify(args.output, args.ffmpeg)
    print(json.dumps(report["cues"], indent=2))


if __name__ == "__main__":
    main()
