"""Synthesize original MIT-licensed Bar cues and measure a padded 400 ms block.

No audio device, third-party sample, random source or network is used. The WAV
files contain only the short cue; zero padding is used for measurement only.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import wave

ROOT = Path(__file__).resolve().parents[1]
RATE = 48000
BLOCK = 19200
# ITU-R BS.1770-5 Annex 1, Tables 1/2, 48 kHz K-weighting filter coefficients.
FILTERS = (
    ((1.53512485958697, -2.69169618940638, 1.19839281085285), (1., -1.69065929318241, .73248077421585)),
    ((1., -2., 1.), (1., -1.99004745483398, .99007225036621)),
)


def filter_samples(samples, b, a):
    x1 = x2 = y1 = y2 = 0.
    output = []
    for value in samples:
        result = b[0] * value + b[1] * x1 + b[2] * x2 - a[1] * y1 - a[2] * y2
        x2, x1, y2, y1 = x1, value, y1, result
        output.append(result)
    return output


def loudness_400ms(samples):
    if not 0 < len(samples) <= BLOCK:
        raise ValueError("The cue must fit in one 400 ms measurement block")
    weighted = list(samples) + [0.] * (BLOCK - len(samples))
    for b, a in FILTERS:
        weighted = filter_samples(weighted, b, a)
    energy = sum(value * value for value in weighted) / BLOCK
    return -.691 + 10 * math.log10(energy) if energy else -math.inf


def pulse(t, duration, frequency, *, decay=.045, sweep=0.):
    if not 0 <= t < duration:
        return 0.
    attack = math.sin(math.pi / 2 * min(t / .002, 1)) ** 2
    tail = math.sin(math.pi / 2 * min((duration - t) / .005, 1)) ** 2
    phase = 2 * math.pi * (frequency * t + sweep * .025 * (1 - math.exp(-t / .025)))
    return attack * tail * math.exp(-t / decay) * math.sin(phase)


def synthesize(name):
    durations = {"start": .096, "end": .080, "command": .112}
    duration = durations[name]
    samples = []
    for frame in range(round(duration * RATE)):
        t = frame / RATE
        if name == "start":
            value = pulse(t, duration, 1050, sweep=550)
        elif name == "end":
            value = pulse(t, duration, 760, decay=.035, sweep=-180)
        else:
            value = pulse(t, .044, 1250, decay=.030) + pulse(t - .060, .052, 1850, decay=.035)
        samples.append(value)
    target = -24. if name == "end" else -18.
    gain = 10 ** ((target - loudness_400ms(samples)) / 20)
    pcm = [round(value * gain * 32768) for value in samples]
    if any(not -32768 <= value <= 32767 for value in pcm):
        raise ValueError("Cue normalization would clip")
    quantized = [value / 32768 for value in pcm]
    peak = 20 * math.log10(max(abs(value) for value in quantized))
    if peak > -1:
        raise ValueError("Cue needs more than 1 dB sample-peak headroom")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(RATE)
        output.writeframes(struct.pack(f"<{len(pcm)}h", *pcm))
    data = buffer.getvalue()
    return data, {"file": f"{name}.wav", "sha256": hashlib.sha256(data).hexdigest(),
        "frames": len(pcm), "duration_ms": len(pcm) / RATE * 1000,
        "target_lufs": target, "padded_400ms_lufs": round(loudness_400ms(quantized), 5),
        "sample_peak_dbfs": round(peak, 5)}


def generate(check=False):
    destination = ROOT / "saydraft/ui/sound_assets"
    cues = {}
    for name in ("start", "end", "command"):
        data, metadata = synthesize(name)
        path = destination / metadata["file"]
        if check:
            if path.read_bytes() != data:
                raise ValueError(f"Stale generated sound: {path.name}")
        else:
            destination.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        cues[name] = metadata
    report = {"schema": 1, "sample_rate": RATE, "channels": 1, "sample_bits": 16,
        "license": "MIT", "generator": "tools/generate_bar_sounds.py",
        "measurement": "BS.1770 K weighting; one 400 ms mono block; cue followed by silence; padding is not in the WAV",
        "cues": cues}
    data = (json.dumps(report, indent=2) + "\n").encode()
    path = destination / "manifest.json"
    if check:
        if path.read_bytes().replace(b"\r\n", b"\n") != data:
            raise ValueError("Stale sound manifest")
    else:
        path.write_bytes(data)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify committed sound bytes and metadata")
    report = generate(parser.parse_args().check)
    print(json.dumps(report["cues"], indent=2))


if __name__ == "__main__":
    main()
