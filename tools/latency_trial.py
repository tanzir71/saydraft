"""One owned fresh-process cold/warm pair; invoked by tools.bench matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import soundfile as sf

from saydraft.asr.language_id import AudioLanguageIdentifier
from saydraft.asr.model_ids import LANGUAGE_ID_MODEL
from saydraft.asr.router import AsrRouter
from saydraft.asr.selection import select_model
from saydraft.asr.sherpa_parakeet import ParakeetEngine
from saydraft.asr.whisper_ct2 import WhisperCT2Engine, WhisperEngineConfig
from saydraft.cleanup.llm.candidates import candidate_directory, candidate_weight, get_candidate
from saydraft.cleanup.llm.sidecar import SidecarManager
from saydraft.config import default_config
from saydraft.core.container import Services
from saydraft.core.interfaces import TargetContext
from saydraft.core.processing import IdentityFormatter, TranscriptProcessor
from saydraft.core.session import DictationSession, SessionState
from saydraft.core.worker import SessionWorker
from saydraft.dictation import DictationConfig, DictationPipeline
from saydraft.dictation.llm_local import LocalLLMConfig, LocalLLMCleaner
from saydraft.history import DictationHistoryStore
from saydraft.insert.inserter import Inserter
from saydraft.models.benchmark import fixture_path
from saydraft.models.downloader import installation_ready
from saydraft.models.manifest import get_model
from saydraft.models.native_devices import select_device
from saydraft.privacy.netguard import NetworkGuard
from saydraft.stt.whisper_engine import _default_model_factory
from tools.bench_cleanup import NativeMeter
from tools.latency_matrix import PHASES, write_json
from tools.latency_environment import require_runtime_versions, runtime_environment
from tools.probe_cleanup_latency import feed_capture, wait_for
from tools.soak_runner import MemoryClipboard, MemoryKeyboard


def cleanup_snapshot(local):
    if local is None:
        return {"state": "disabled", "decoder": {}}
    manager, preparation, client = local._manager, local._preparation, local._client
    measurement = client.decoder.current if client is not None else None
    return {"sidecar": manager.status if manager else None,
        "preparation": preparation.status if preparation else None,
        "decoder": measurement.metadata() if measurement is not None else {}}


class CheckedDelivery:
    """Timestamp the simulated paste only after this utterance is durable."""

    def __init__(self, history, *, clock=time.monotonic):
        self.history, self.clock = history, clock
        self.clipboard = MemoryClipboard()
        self.clipboard.copy("latency clipboard sentinel")
        self.keyboard = MemoryKeyboard(self.before_paste)
        self.released_at, self.expected_id, self.pasted_at = None, 0, None

    def begin(self, expected_id):
        self.released_at, self.pasted_at, self.expected_id = None, None, expected_id

    def before_paste(self, hotkey):
        rows = self.history.list_recent(limit=1)
        if (hotkey != "ctrl+v" or self.released_at is None or self.pasted_at is not None or not rows
                or rows[0].id != self.expected_id or not rows[0].raw_text
                or rows[0].cleaned_text != self.clipboard.paste()):
            raise RuntimeError("Latency paste lacks release and current durable History")
        self.pasted_at = self.clock()


def replay_asr(spec, config):
    """Use the written tier's production engine, preserving its reported model ID."""
    if spec['tier'] == 'lite':
        directory = Path(spec['whisper_dir'])
        if not installation_ready(get_model('whisper-base'), directory, check_hashes=True):
            raise ValueError('Pinned Whisper base bundle is incomplete or changed')
        select_model(config, 'whisper-base')
        primary = WhisperCT2Engine(WhisperEngineConfig.from_app_config(config),
            model_factory=lambda _name, **kwargs: _default_model_factory(str(directory), **kwargs))
        return primary, primary
    if not installation_ready(get_model(LANGUAGE_ID_MODEL), Path(spec['lid_dir']), check_hashes=True):
        raise ValueError('Pinned language identification bundle is incomplete or changed')
    primary = ParakeetEngine(model_dir=spec['parakeet_dir'])
    router = AsrRouter(config, engine_factory=lambda _settings, _route: primary, installed=lambda _model: False,
        language_identifier=AudioLanguageIdentifier(model_dir=spec['lid_dir']))
    return primary, router


def run_trial(spec):
    output = Path(spec["output"])
    report = {"schema": 1, **{name: spec[name] for name in ("git_commit", "audio_seconds", "repeat", "tier", "asr_model")},
        'runtime_environment': runtime_environment(),
        "cases": [], "native_exits": [], "complete": False}
    meter, worker, pipeline, local = None, None, None, None
    started = time.monotonic()
    NetworkGuard.install()
    try:
        if report['runtime_environment'] != spec.get('runtime_environment'):
            raise ValueError('Trial runtime environment differs from its parent request')
        require_runtime_versions(report['runtime_environment'], spec['tier'])
        meter = NativeMeter()
        if spec.get("vad_dir"):
            from saydraft.model_download import default_models_dir, model_relative_dir

            model = get_model("silero-vad-v5")
            if not installation_ready(model, Path(spec["vad_dir"]), check_hashes=True):
                raise ValueError("Silero bundle is incomplete or changed")
            target = default_models_dir() / model_relative_dir(model)
            shutil.copytree(spec["vad_dir"], target)
            report["vad"] = "pinned Silero in private QA profile; production fallback remains enabled"
        else:
            report["vad"] = "WebRTC fallback; debug only"
        source_audio, rate = sf.read(fixture_path(), dtype="float32")
        if rate != 16000 or source_audio.shape != (128000,) or not np.isfinite(source_audio).all():
            raise ValueError("Invalid bundled fixture")
        report["source_fixture_sha256"] = hashlib.sha256(fixture_path().read_bytes()).hexdigest()
        seconds = spec["audio_seconds"]
        audio = np.tile(source_audio, int(np.ceil(seconds / 8)))[:seconds * rate]
        report["replay_samples_sha256"] = hashlib.sha256(audio.tobytes()).hexdigest()
        config = default_config()
        config["stt"]["background_transcription"] = True
        config["dictation"]["mode"] = "balanced" if spec["tier"] == "lite" else "aggressive"
        cfg = LocalLLMConfig()
        if spec["candidate"] is not None:
            candidate = get_candidate(spec["candidate"])
            weight = candidate_weight(candidate, candidate_directory(spec["models_dir"], candidate))
            cfg = LocalLLMConfig(enabled=True, model_path=str(weight), backend=spec["backend"], n_threads=4)
            local = LocalLLMCleaner(cfg, manager_factory=lambda settings: SidecarManager(
                replace(settings, device=spec["device"]), resolver=lambda _name: Path(spec["runtime_dir"]),
                process_factory=meter.spawn, device_selector=lambda *a, **kw: select_device(
                    *a, **kw, process_factory=meter.spawn)))
        pipeline = DictationPipeline(DictationConfig(llm=cfg), **({"llm_cleaner": local} if local else {}))
        history = DictationHistoryStore(output / "history.db")
        delivery = CheckedDelivery(history)
        inserter = Inserter(clipboard=delivery.clipboard, keyboard=delivery.keyboard,
            focus_provider=lambda: "fixture", restore_delay=.15)
        primary, router = replay_asr(spec, config)
        capture = SimpleNamespace(sample_rate=rate, audio=audio, chunk_callback=None,
            start=lambda: None, stop=lambda: audio.copy())
        formatter = IdentityFormatter()
        processor = TranscriptProcessor(cleaner=pipeline, formatter=formatter, history=history, inserter=inserter)
        services = Services(config, capture, router, pipeline, formatter, inserter,
            SimpleNamespace(capture=lambda: TargetContext("fixture", "Fixture QA")), history, processor, [])
        worker = SessionWorker(services, session=DictationSession(clock=time.monotonic))
        report["service_setup_seconds"] = time.monotonic() - started
        with (output / "cases.jsonl").open("x", encoding="utf-8") as journal:
            for index, phase in enumerate(PHASES, 1):
                delivery.begin(index)
                arm_started = time.monotonic()
                if not worker.start_recording():
                    raise RuntimeError("Worker refused capture")
                wait_for(lambda: worker.session.state != SessionState.ARMING)
                armed = time.monotonic()
                if worker.session.state != SessionState.LISTENING:
                    raise RuntimeError("Worker did not arm")
                identifier = getattr(router, '_language_identifier', None)
                lid_ready = getattr(identifier, '_model', None) is not None if identifier is not None else None
                if identifier is not None and not lid_ready:
                    raise RuntimeError('Language identification did not prepare')
                at_capture = cleanup_snapshot(local)
                feed_started = time.monotonic()
                feed_capture(capture, clock=time.monotonic, deliver_after_frame=True)
                captured = time.monotonic()
                no_early = delivery.pasted_at is None and len(history.list_recent()) == index - 1
                if not no_early:
                    raise RuntimeError("Worker delivered before release")
                delivery.released_at = captured
                worker.stop_recording(released_at=delivery.released_at)
                at_release = cleanup_snapshot(local)
                at_release["observed_after_release_seconds"] = time.monotonic() - delivery.released_at
                wait_for(lambda: not worker.busy, 120)
                settled = time.monotonic()
                rows = history.list_recent(limit=1)
                result = worker.last_result
                if (delivery.pasted_at is None or not rows or rows[0].id != index or result is None
                        or result.insertion.status != "inserted" or delivery.keyboard.written
                        or delivery.clipboard.paste() != "latency clipboard sentinel"):
                    raise RuntimeError("Worker did not finish checked memory delivery")
                row = rows[0]
                item = {"phase": phase, "audio_seconds": seconds, "repeat": spec["repeat"],
                    "fed_samples": len(audio), "arming_seconds": armed - arm_started,
                    "capture_seconds": captured - feed_started, "asr_load_seconds": getattr(primary, 'load_seconds', None),
                    "release_to_paste_seconds": delivery.pasted_at - delivery.released_at,
                    "release_to_settled_seconds": settled - delivery.released_at,
                    "history_before_paste": True, "clipboard_restored": True, "no_early_delivery": no_early,
                    "release_deadline_present": worker._context.cleanup_deadline is not None,
                    "decision": row.llm_decision, "asr_model": row.model, "timings": json.loads(row.timings_json),
                    "language_identifier_ready": lid_ready,
                    "cleanup_at_capture": at_capture, "cleanup_at_release": at_release,
                    "cleanup_after_delivery": cleanup_snapshot(local), "cleanup_gate": local.last_gate_info if local else None}
                report["cases"].append(item)
                journal.write(json.dumps(item, allow_nan=False) + "\n")
                journal.flush()
                write_json(output / "report.json", report)
    except Exception as exc:
        report["error_type"] = type(exc).__name__
        trace = exc.__traceback__
        while trace.tb_next is not None:
            trace = trace.tb_next
        report["error_location"] = {"file": Path(trace.tb_frame.f_code.co_filename).name, "line": trace.tb_lineno}
    finally:
        report["selected_device"] = local._manager.selected_device if local is not None and local._manager is not None else None
        if meter is not None:
            try:
                report["native_peak_rss_bytes"] = meter.peaks()
            except Exception as exc:
                report["memory_error_type"] = type(exc).__name__
        try:
            if worker is not None:
                worker.shutdown()
                worker.executor.shutdown(wait=True)
            elif pipeline is not None:
                pipeline.close()
            elif local is not None:
                local.close()
        except Exception as exc:
            report["shutdown_error_type"] = type(exc).__name__
        try:
            if meter is not None:
                report["native_exits"] = meter.finish()
        except Exception as exc:
            report["shutdown_error_type"] = type(exc).__name__
        finally:
            NetworkGuard.uninstall()
        report["elapsed_seconds"] = time.monotonic() - started
        report["complete"] = (len(report["cases"]) == 2 and not report.get("error_type")
            and not report.get("shutdown_error_type") and all(report["native_exits"])
            and (spec["tier"] == "lite" or bool(report["native_exits"]))
            and all(row['asr_model'] == spec['asr_model'] for row in report['cases']))
        write_json(output / "report.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args(argv)
    report = run_trial(json.loads(args.request.read_text(encoding="utf-8")))
    print(json.dumps({"complete": report["complete"], "cases": len(report["cases"])}))
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
