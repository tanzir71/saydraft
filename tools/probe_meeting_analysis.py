"""Analyze two pinned public fixture tracks into independent local meeting Notes.

No device capture, playback, clipboard, foreground reads, hooks or downloads.
The recording events are a file fixture, not microphone/WASAPI qualification.
Speech, VAD, speaker and summary inference use the actual verified native models.
"""

import argparse
from contextlib import contextmanager
import ctypes as c
from ctypes import wintypes as w
from dataclasses import asdict
from datetime import datetime, timezone
import gc
import hashlib
import json
import math
from pathlib import Path
import socket
import subprocess
import time
import uuid

import soundfile as sf

from saydraft.asr.sherpa_parakeet import ParakeetConfig, ParakeetEngine
from saydraft.audio.vad_silero import SileroVad
from saydraft.cleanup.llm.loopback import LoopbackClient
from saydraft.cleanup.llm.sidecar import SidecarConfig, SidecarManager
from saydraft.cleanup.llm.windows_process import WindowsJobProcess
from saydraft.data.notes import NoteStore
from saydraft.meetings.diarization import SpeakerDiarizer
from saydraft.meetings.notes import MeetingNoteDraft
from saydraft.meetings.process import CaptureOutcome
from saydraft.meetings.protocol import AudioChunk, CaptureEnd, CaptureEvent, TrackStarted
from saydraft.meetings.summary import SummaryClient
from saydraft.meetings.timeline import MeetingAudioBuffer
from saydraft.meetings.transcription import MeetingTranscriber
from saydraft.models.downloader import installation_ready
from saydraft.models.layout import require_local_paths
from saydraft.models.manifest import get_model
from saydraft.privacy.netguard import NetworkGuard

ROOT = Path(__file__).resolve().parents[1]
MODEL_IDS = ('parakeet-tdt-0-6b-v3-int8', 'silero-vad-v5', 'pyannote-segmentation-3-0',
             '3dspeaker-eres2net-base', 'qwen35-4b-q4-k-m', 'llama-cpp-b12110-cpu-x64')


def digest(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


class OwnedProcessMeter:
    def __init__(self):
        self.handles, self.pids = [], []
        self.api = c.WinDLL('kernel32', use_last_error=True, winmode=0x800)
        for name, result, args in (
            ('OpenProcess', w.HANDLE, [w.DWORD, w.BOOL, w.DWORD]),
            ('WaitForSingleObject', w.DWORD, [w.HANDLE, w.DWORD]),
            ('CloseHandle', w.BOOL, [w.HANDLE]),
        ):
            function = getattr(self.api, name)
            function.restype, function.argtypes = result, args

    def spawn(self, argv, **kwargs):
        process = WindowsJobProcess(argv, **kwargs)
        handle = self.api.OpenProcess(0x100000, False, process.pid)
        if not handle:
            process.close()
            raise c.WinError(c.get_last_error())
        self.handles.append(handle)
        self.pids.append(process.pid)
        return process

    def finish(self):
        try:
            return [self.api.WaitForSingleObject(handle, 3000) == 0 for handle in self.handles]
        finally:
            for handle in self.handles:
                self.api.CloseHandle(handle)
            self.handles.clear()


class RecordedClient:
    """Retain public-fixture responses; authentication and native environment stay private."""
    def __init__(self, port, token, output):
        self.inner, self.output, self.index = LoopbackClient(port, token), output, 0

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def request_json(self, path, **kwargs):
        return self.inner.request_json(path, **kwargs)

    @contextmanager
    def response_bytes(self, path, **kwargs):
        self.index += 1
        payload = kwargs.get('payload', {})
        (self.output / f'request-{self.index}.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                                             encoding='utf-8')
        with self.inner.response_bytes(path, **kwargs) as chunks, (self.output / f'completion-{self.index}.sse').open('xb') as log:
            def record():
                for chunk in chunks:
                    log.write(chunk)
                    log.flush()
                    yield chunk
            yield record()


def run_probe(args):
    NetworkGuard.install()
    require_local_paths(args.output, args.model_paths, args.corpus, args.microphone_audio, args.desktop_audio)
    paths = json.loads(args.model_paths.read_text(encoding='utf-8'))
    if set(paths) != set(MODEL_IDS):
        raise ValueError('Supply exactly the six pinned analysis model/runtime directories')
    paths = {name: Path(value).resolve() for name, value in paths.items()}
    require_local_paths(*paths.values())
    for name, path in paths.items():
        if not installation_ready(get_model(name), path, check_hashes=True):
            raise ValueError('Explicit native model/runtime cache did not verify: ' + name)
    corpus = json.loads(args.corpus.read_text(encoding='utf-8'))
    if (corpus.get('dataset'), corpus.get('revision'), corpus.get('license')) != (
            'google/fleurs', '70bb2e84b976b7e960aa89f1c648e09c59f894dd', 'CC-BY-4.0'):
        raise ValueError('This smoke requires the already licensed pinned FLEURS fixture metadata')
    clips = {clip['sha256']: clip for clip in corpus['clips']}
    files = [*sorted((ROOT / 'saydraft/meetings').glob('*.py')), Path(__file__).resolve(),
             ROOT / 'saydraft/models/manifest.json', ROOT / 'saydraft/asr/sherpa_parakeet.py',
             ROOT / 'saydraft/audio/vad_silero.py', ROOT / 'saydraft/data/notes.py']
    fingerprints = {path.relative_to(ROOT).as_posix(): digest(path) for path in files}
    args.output.mkdir(parents=True, exist_ok=False)
    report = {'schema': 1, 'measured_at': datetime.now(timezone.utc).isoformat(),
        'scope': 'native file-fixture analysis through meeting Notes; no live device/GUI/30-minute acceptance',
        'source': {'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                   'dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip()),
                   'sha256': fingerprints},
        'models': {name: {'revision': get_model(name)['revision'], 'verified_before': True,
                         'license': get_model(name)['license']} for name in MODEL_IDS},
        'corpus': {'dataset': corpus['dataset'], 'revision': corpus['revision'], 'license': corpus['license'],
                   'sha256': digest(args.corpus)}, 'inputs': [], 'capture': 'synthetic file events',
        'native_firewall_verified': False, 'passed': False}
    manager = None
    meter = OwnedProcessMeter()
    try:
        waveforms = []
        for track, path in (('microphone', args.microphone_audio), ('desktop', args.desktop_audio)):
            checksum = digest(path)
            clip = clips.get(checksum)
            info = sf.info(path)
            if clip is None or info.samplerate != 16000 or info.channels != 1 or not 0 < info.frames <= 60 * 16000:
                raise ValueError('Explicit fixture audio does not match the pinned corpus')
            waveform, rate = sf.read(path, dtype='float32')
            if rate != 16000 or len(waveform) != clip['num_samples'] or digest(path) != checksum:
                raise ValueError('Fixture changed or has inconsistent audio metadata')
            waveforms.append((track, waveform))
            report['inputs'].append({'track': track, 'path': str(path), 'sha256': checksum,
                                     'frames': len(waveform), 'reference': clip['reference']})
        buffer = MeetingAudioBuffer(max_seconds=math.ceil(max(len(waveform) for _, waveform in waveforms) / 16000))
        for track, _ in waveforms:
            buffer.consume(CaptureEvent('track', TrackStarted(track, 0.)))
        buffer.consume(CaptureEvent('ready'))
        for track, waveform in waveforms:
            for start in range(0, len(waveform), 1600):
                buffer.consume(CaptureEvent('audio', AudioChunk(track, start, waveform[start:start + 1600])))
        end = CaptureEnd(True, 'stopped', *(len(waveform) for _, waveform in waveforms))
        buffer.consume(CaptureEvent('end', end))
        audio = buffer.freeze(CaptureOutcome(True, True, 'stopped', 0, end=end))
        del buffer, waveforms, waveform
        started = time.perf_counter()
        transcriber = MeetingTranscriber(
            ParakeetEngine(ParakeetConfig(silence_trim=False), model_dir=paths[MODEL_IDS[0]]),
            SpeakerDiarizer(resolver=lambda name, **_kwargs: paths.get(name)),
            detector_factory=lambda: SileroVad(paths['silero-vad-v5'] / 'silero_vad.onnx'))
        transcript = transcriber.transcribe(audio)
        report['transcribe_seconds'] = time.perf_counter() - started
        report['transcript'] = asdict(transcript)
        del transcriber, audio
        gc.collect()  # Drop the meeting PCM/ASR sessions before the 4B summary model.
        print(json.dumps({'transcription_complete': transcript.complete, 'utterances': len(transcript.utterances)}), flush=True)
        weight = next(file['path'] for file in get_model('qwen35-4b-q4-k-m')['files'] if file['path'].endswith('.gguf'))
        manager = SidecarManager(SidecarConfig((paths['qwen35-4b-q4-k-m'] / weight).resolve(), backend='cpu',
            threads=4, context_size=4096, startup_seconds=60, max_restarts=0),
            resolver=lambda name: paths.get(name), capability_check=lambda backend: backend == 'cpu',
            process_factory=meter.spawn, client_factory=lambda port, token: RecordedClient(port, token, args.output))
        if not manager.prepare():
            raise RuntimeError('Verified local summary runtime could not prepare: ' + str(manager.status))
        started = time.perf_counter()
        reply = SummaryClient(manager).summarize(transcript, timeout=120)
        report['summary_seconds'] = time.perf_counter() - started
        report['summary'] = asdict(reply)
        store = NoteStore(args.output / 'public-notes.db')
        primary = store.save(uuid.uuid4().hex, 'Public fixture Scratchpad; preserve this active draft.')
        draft = MeetingNoteDraft.create(transcript, reply.summary)
        saved = draft.save(store)
        assert draft.save(store) == saved and store.active() == primary
        (args.output / 'meeting.md').write_text(saved.body, encoding='utf-8')
        report['notes'] = {'id': saved.id, 'kind': saved.kind, 'revision': saved.revision,
                           'active_scratchpad_unchanged': store.active() == primary,
                           'retry_same_note': len(store.list()) == 2, 'markdown_sha256': digest(args.output / 'meeting.md')}
        try:
            socket.getaddrinfo('example.com', 443)
        except PermissionError:
            report['python_network_policy'] = True
        else:
            raise RuntimeError('Python offline policy was not installed')
        report['passed'] = bool(transcript.complete and transcript.utterances and reply.reason == 'ok' and reply.summary)
    except BaseException as error:
        report['error'] = {'type': type(error).__name__, 'message': str(error)}
    finally:
        if manager is not None:
            manager.close()
        report['native_exits'] = meter.finish()
        report['native_pids'] = meter.pids
        for name, path in paths.items():
            report['models'][name]['verified_after'] = installation_ready(get_model(name), path, check_hashes=True)
        report['source_unchanged'] = fingerprints == {path.relative_to(ROOT).as_posix(): digest(path) for path in files}
        report['passed'] = bool(report['passed'] and report['source_unchanged'] and report['native_exits']
                                and all(report['native_exits']) and all(item['verified_after'] for item in report['models'].values()))
        (args.output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'passed': report['passed'], 'summary_reason': report.get('summary', {}).get('reason'),
                      'native_exits': report['native_exits']}), flush=True)
    return 0 if report['passed'] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-paths', type=Path, required=True)
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--microphone-audio', type=Path, required=True)
    parser.add_argument('--desktop-audio', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    return run_probe(parser.parse_args(argv))


if __name__ == '__main__':
    raise SystemExit(main())
