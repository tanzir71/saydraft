"""Native cleanup fallback/shutdown soak with fixture capture and insertion stubs.

Explicit verified local runtime/model paths only; no microphone, OS insertion or
downloads. The deliberately one-token fixture supplies no cleanup-quality claim.
All reports and SQLite rows stay in a fresh QA output directory.
"""

import argparse
import ctypes as c
import hashlib
import json
import os
import time
from ctypes import wintypes as w
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from saydraft.cleanup.llm.loopback import LoopbackClient
from saydraft.cleanup.llm.sidecar import SidecarManager
from saydraft.cleanup.llm.windows_process import WindowsJobProcess
from saydraft.config import default_config
from saydraft.core.container import Services
from saydraft.core.interfaces import TargetContext
from saydraft.core.processing import IdentityFormatter, TranscriptProcessor
from saydraft.core.session import DictationSession
from saydraft.core.worker import SessionWorker
from saydraft.dictation import DictationConfig, DictationContext, DictationPipeline
from saydraft.dictation.glossary import Glossary
from saydraft.dictation.llm_local import LocalLLMConfig, LocalLLMCleaner
from saydraft.history import DictationHistoryStore
from saydraft.insert.inserter import InsertionResult
from saydraft.privacy.netguard import NetworkGuard


class InlineExecutor:
    def submit(self, callback, *args):
        callback(*args)

    def shutdown(self, **kwargs):
        pass


def expected_outcomes(cycles):
    # Deadline fallback is an intended result, while an ordinary HTTP/protocol
    # failure must not masquerade as successful streaming integration.
    return (any(row["decision"] == "incomplete" and not row["termination_after_tokenization"] for row in cycles)
        and all(row["decision"] in ({"unavailable", "timeout"} if row["termination_after_tokenization"]
                                    else {"incomplete", "timeout"}) for row in cycles))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("runtime-dir", "model", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--backend", choices=("cpu", "vulkan"), default="cpu")
    parser.add_argument("--cycles", type=int, default=10)
    parser.add_argument("--fixture-context-override", action="store_true",
                        help="developer-only: expand the pinned tiny fixture's declared context to 4096")
    args = parser.parse_args(argv)
    if os.name != "nt" or not 2 <= args.cycles <= 100:
        parser.error("Windows and 2–100 cycles are required")
    if args.output.exists():
        parser.error("choose a fresh QA output directory")
    with args.model.open("rb") as model_file:
        model_sha = hashlib.file_digest(model_file, "sha256").hexdigest()
    if args.fixture_context_override and model_sha != "6151b1929d7f5aa3385d9ddef3393e55587c0a55de661562322bc51dfda93a04":
        parser.error("context override is restricted to the pinned developer fixture")
    args.output.mkdir(parents=True)
    kernel = c.WinDLL("kernel32", use_last_error=True)
    for name, restype, argtypes in (
            ("OpenProcess", w.HANDLE, [w.DWORD, w.BOOL, w.DWORD]),
            ("WaitForSingleObject", w.DWORD, [w.HANDLE, w.DWORD]),
            ("CloseHandle", w.BOOL, [w.HANDLE])):
        function = getattr(kernel, name)
        function.restype, function.argtypes = restype, argtypes
    observers, managers, inserted, cycles = [], [], [], []
    control = SimpleNamespace(kill=False, clock=0.0)
    worker = None

    def spawn(*values, **kwargs):
        if args.fixture_context_override:
            values = ([*values[0], "--override-kv", "llama.context_length=int:4096"], *values[1:])
        process = WindowsJobProcess(*values, **kwargs)
        handle = kernel.OpenProcess(0x100000, False, process.pid)
        if not handle:
            process.close()
            raise c.WinError(c.get_last_error())
        observers.append(handle)
        return process

    class FaultClient(LoopbackClient):
        def request_json(self, path, **kwargs):
            result = super().request_json(path, **kwargs)
            if path == "/tokenize" and kwargs.get("payload", {}).get("content") and control.kill:
                # Terminate after tokenization, before the streaming HTTP request.
                # Native mid-generation interruption is checked separately.
                managers[-1]._process.terminate()
            return result

    def manager_factory(config):
        manager = SidecarManager(config, resolver=lambda name: args.runtime_dir.resolve(),
            process_factory=spawn, client_factory=FaultClient)
        managers.append(manager)
        return manager

    history = DictationHistoryStore(args.output / "history.db")
    raw = "um send 2 files to Saydraft"
    cfg = LocalLLMConfig(enabled=True, model_path=str(args.model.resolve()), backend=args.backend,
                         n_threads=1, max_tokens=1)
    cleaner = DictationPipeline(DictationConfig(llm=cfg), llm_cleaner=LocalLLMCleaner(
        cfg, manager_factory=manager_factory))
    cleaner.glossary = Glossary(user_terms=("Saydraft",))
    baseline = DictationPipeline(DictationConfig())
    baseline.glossary = cleaner.glossary
    expected = baseline.process_transcript(raw, DictationContext())

    def insert(text, **kwargs):
        assert len(history.list_recent(limit=100)) == len(inserted) + 1
        inserted.append(text)
        return InsertionResult("inserted", "fixture")

    inserter = SimpleNamespace(insert_text=insert)
    formatter = IdentityFormatter()
    processor = TranscriptProcessor(cleaner=cleaner, formatter=formatter, history=history, inserter=inserter)
    services = Services(default_config(),
        SimpleNamespace(start=lambda: None, stop=lambda: np.ones(16000, dtype=np.float32)),
        SimpleNamespace(transcribe=lambda audio: raw), cleaner, formatter, inserter,
        SimpleNamespace(capture=lambda: TargetContext("fixture", "Cleanup QA")), history, processor, [])
    NetworkGuard.install()
    try:
        worker = SessionWorker(services, executor=InlineExecutor(),
                               session=DictationSession(clock=lambda: control.clock))
        for index in range(args.cycles):
            # Alternate cleaner replacements to exercise settings-style handoffs.
            if index and index % 2 == 0:
                cleaner.close()
                cleaner.llm = LocalLLMCleaner(cfg, manager_factory=manager_factory)
            cleaner.warm()
            manager = managers[-1]
            deadline = time.monotonic() + 20
            while not manager.ready and time.monotonic() < deadline:
                manager.prepare()
                time.sleep(0.01)
            assert manager.ready, manager.status
            control.kill = bool(index % 2)
            assert worker.start_recording()
            control.clock += 1
            started = time.perf_counter()
            worker.stop_recording()
            elapsed = time.perf_counter() - started
            result = worker.last_result
            assert result and result.cleaned_text == expected and result.insertion.status == "inserted"
            assert cleaner.last_llm_decision != "accepted"
            cycles.append({"cycle": index, "termination_after_tokenization": control.kill,
                "decision": cleaner.last_llm_decision, "release_seconds": elapsed,
                "rules_preserved": True})
        worker.shutdown()
        exited = all(kernel.WaitForSingleObject(handle, 2000) == 0 for handle in observers)
        assert exited, "owned cleanup process survived worker shutdown"
        rows = history.list_recent(limit=100)
        normal_stream_count = sum(row["decision"] == "incomplete" and not row["termination_after_tokenization"]
                                  for row in cycles)
        report = {"offline": True, "microphone_used": False, "os_insertion_used": False,
            "quality_claim": False, "cycles": cycles, "history_rows": len(rows),
            "stub_insertions": len(inserted), "processes_started": len(observers),
            "model_sha256": model_sha, "fixture_context_override": args.fixture_context_override,
            "normal_length_limited_streams_checked": normal_stream_count,
            "deadline_fallbacks": sum(row["decision"] == "timeout" for row in cycles),
            "all_processes_exited_after_shutdown": exited,
            "passed": len(rows) == args.cycles == len(inserted) and exited and expected_outcomes(cycles)}
        (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report))
        return 0 if report["passed"] else 1
    finally:
        if worker is not None:
            worker.shutdown()
        cleaner.close()
        for manager in managers:
            manager.close()
        for handle in observers:
            kernel.CloseHandle(handle)
        NetworkGuard.uninstall()


if __name__ == "__main__":
    raise SystemExit(main())
