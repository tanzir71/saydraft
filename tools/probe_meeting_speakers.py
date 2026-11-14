"""Offline speaker-model smoke with explicit local files; never records or downloads.

Multiple inputs are concatenated with a one-second silent separator. This proves
the installed native path runs; it does not score diarization error or establish
the number or identity of people without independently annotated references.
"""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import time

import numpy as np
import soundfile as sf

from saydraft.meetings.diarization import SpeakerDiarizer
from saydraft.meetings.limits import MAX_ANALYSIS_SAMPLES
from saydraft.meetings.models import speaker_bundle
from saydraft.meetings.request import MAX_SECONDS
from saydraft.models.downloader import installation_ready
from saydraft.models.layout import model_relative_dir, require_local_paths
from saydraft.privacy.netguard import NetworkGuard


def digest(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def run_probe(model_root, paths, *, num_speakers=-1):
    if not paths or len(paths) > 32:
        raise ValueError('Supply 1–32 explicit local mono 16 kHz audio files')
    NetworkGuard.install()
    source = Path(__file__).resolve().parents[1]
    files = ['tools/probe_meeting_speakers.py', 'saydraft/meetings/diarization.py',
             'saydraft/meetings/models.py', 'saydraft/models/manifest.py', 'saydraft/models/manifest.json']
    fingerprints = {name: digest(source / name) for name in files}
    root = Path(model_root).resolve()
    require_local_paths(root, *paths)
    models, directories = [], {}
    for model in speaker_bundle():
        directory = root / model_relative_dir(model)
        if not installation_ready(model, directory, check_hashes=True):
            raise ValueError('Explicit model directory lacks the verified meeting speaker package')
        directories[model['id']] = directory
        models.append({'id': model['id'], 'revision': model['revision'], 'license': model['license'],
                       'files': [{'path': file['path'], 'sha256': digest(directory / file['path']),
                                  'bytes': (directory / file['path']).stat().st_size} for file in model['files']]})
    parts, inputs, cursor = [], [], 0
    for supplied in paths:
        path = Path(supplied).resolve()
        info = sf.info(path)
        if (info.samplerate != 16000 or info.channels != 1 or not 0 < info.frames <= MAX_SECONDS * 16000
                or cursor + info.frames + (16000 if parts else 0) > MAX_ANALYSIS_SAMPLES):
            raise ValueError('Probe input must fit the mono 16 kHz meeting duration bound')
        if parts:
            parts.append(np.zeros(16000, np.float32))
            cursor += 16000
        audio_hash = digest(path)
        waveform, rate = sf.read(path, dtype='float32')
        if rate != 16000 or waveform.ndim != 1 or len(waveform) != info.frames:
            raise ValueError('Probe input changed while reading')
        if digest(path) != audio_hash:
            raise ValueError('Probe input bytes changed while reading')
        inputs.append({'path': str(path), 'sha256': audio_hash, 'frames': len(waveform),
                       'timeline_start': cursor / 16000})
        parts.append(waveform)
        cursor += len(waveform)
    waveform = np.concatenate(parts)
    engine = SpeakerDiarizer(resolver=lambda identifier, **_kwargs: directories.get(identifier),
                            num_speakers=num_speakers)
    started = time.perf_counter()
    engine.prepare()
    load_seconds = time.perf_counter() - started
    started = time.perf_counter()
    turns = engine.diarize(waveform)
    process_seconds = time.perf_counter() - started
    if fingerprints != {name: digest(source / name) for name in files}:
        raise ValueError('Probe source changed during inference')
    for model, identity in zip(speaker_bundle(), models, strict=True):
        directory = directories[model['id']]
        if (not installation_ready(model, directory, check_hashes=True)
                or any(digest(directory / file['path']) != file['sha256'] for file in identity['files'])):
            raise ValueError('Probe model changed during inference')
    blocked = False
    try:
        import socket
        socket.getaddrinfo('example.com', 443)
    except PermissionError:
        blocked = True
    if not blocked:
        raise RuntimeError('NetworkGuard did not block the offline DNS check')
    return {'schema': 1, 'measured_at': datetime.now(timezone.utc).isoformat(),
            'scope': 'native speaker-model smoke, not meeting acceptance or diarization quality',
            'source': {'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip(),
                       'dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=source, text=True).strip()),
                       'sha256': fingerprints},
            'sherpa_onnx': importlib.metadata.version('sherpa-onnx'), 'models': models,
            'inputs': inputs, 'transformation': 'float32 concatenation with one-second silence between inputs',
            'audio_seconds': len(waveform) / 16000, 'num_speakers_setting': num_speakers,
            'load_seconds': load_seconds, 'process_seconds': process_seconds,
            'python_network_policy': blocked, 'native_firewall_verified': False,
            'speaker_clusters': len({turn.speaker for turn in turns}), 'turns': [asdict(turn) for turn in turns]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models', type=Path, required=True)
    parser.add_argument('--audio', type=Path, action='append', required=True)
    parser.add_argument('--num-speakers', type=int, default=-1)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error('Choose a new output path; previous evidence is preserved')
    report = run_probe(args.models, args.audio, num_speakers=args.num_speakers)
    with args.output.open('x', encoding='utf-8') as target:
        target.write(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'speaker_clusters': report['speaker_clusters'], 'turns': len(report['turns']),
                      'audio_seconds': report['audio_seconds'], 'process_seconds': report['process_seconds']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
