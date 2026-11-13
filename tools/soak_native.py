"""Native cleanup cycles with owned processes and synthetic device boundaries."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from tools.soak_runner import SyntheticCycleRunner

FIXTURE_SHA256 = "6151b1929d7f5aa3385d9ddef3393e55587c0a55de661562322bc51dfda93a04"


def expected_outcomes(cycles):
    """Retained fallback classification; native reports also require stream evidence."""
    return (any(row["decision"] == "incomplete" and not row["termination_after_tokenization"] for row in cycles)
        and all(row["decision"] in ({"unavailable", "timeout"} if row["termination_after_tokenization"]
                                    else {"incomplete", "timeout"}) for row in cycles))


class StreamEvidence:
    """Observe SSE metadata while passing the original bytes to CleanupClient."""

    def __init__(self):
        self.pending, self.data = b"", []
        self.done = self.visible = self.tools = self.invalid = False
        self.finish = None

    def feed(self, chunk):
        self.pending += chunk
        if len(self.pending) > 1024*1024:
            self.invalid, self.pending = True, b""
            return
        while b"\n" in self.pending:
            line, self.pending = self.pending.split(b"\n", 1)
            line = line.rstrip(b"\r")
            if line.startswith(b"data:"):
                self.data.append(line[5:].lstrip(b" "))
            elif not line and self.data:
                value, self.data = b"\n".join(self.data), []
                if value == b"[DONE]":
                    self.done = True
                    continue
                try:
                    event = json.loads(value)
                    if not isinstance(event, dict) or "error" in event:
                        raise ValueError("Invalid event")
                    choices = event.get("choices", [])
                    if not isinstance(choices, list) or len(choices) > 1:
                        raise ValueError("Invalid choices")
                    for choice in choices:
                        if not isinstance(choice, dict) or choice.get("index", 0) != 0:
                            raise ValueError("Invalid choice")
                        delta = choice.get("delta", {})
                        if (not isinstance(delta, dict) or delta.get("role", "assistant") != "assistant"
                                or delta.get("content") is not None and not isinstance(delta["content"], str)
                                or choice.get("finish_reason") is not None and not isinstance(choice["finish_reason"], str)):
                            raise ValueError("Invalid delta")
                        self.visible = self.visible or bool(delta.get("content"))
                        self.tools = self.tools or bool(delta.get("tool_calls") or delta.get("function_call"))
                        if choice.get("finish_reason") is not None:
                            self.finish = choice["finish_reason"]
                except (ValueError, TypeError, AttributeError):
                    self.invalid = True

    @property
    def complete(self):
        return self.done and self.visible and self.finish == "length" and not self.tools and not self.invalid


class NativeCycleRunner(SyntheticCycleRunner):
    fail_fast = True

    def __init__(self, *, runtime_dir, model, output, backend="cpu", device=None,
                 fixture_context_override=False):
        if os.name != "nt":
            raise ValueError("Native cleanup soak requires Windows")
        from saydraft.cleanup.llm.loopback import LoopbackClient
        from saydraft.cleanup.llm.sidecar import SidecarManager
        from saydraft.dictation import DictationConfig, DictationContext, DictationPipeline
        from saydraft.dictation.glossary import Glossary
        from saydraft.dictation.llm_local import LocalLLMConfig, LocalLLMCleaner
        from saydraft.models.native_devices import select_device
        from tools.bench_cleanup import NativeMeter

        model, runtime_dir, output = Path(model).resolve(), Path(runtime_dir).resolve(), Path(output).resolve()
        if not model.is_file() or not runtime_dir.is_dir():
            raise ValueError("Explicit installed model and runtime paths are required")
        with model.open("rb") as stream:
            model_sha = hashlib.file_digest(stream, "sha256").hexdigest()
        if fixture_context_override and model_sha != FIXTURE_SHA256:
            raise ValueError("Context override is restricted to the pinned developer fixture")
        output.mkdir(parents=True, exist_ok=False)
        self.output = output
        self.managers, self.cycles = [], []
        self._native_closed, self._native_exits, self._native_close_errors = False, [], []
        self._prepared_index, self._fault_requested, self._fault_injected = None, False, False
        self._tap = StreamEvidence()
        self.preparation_failure = None
        self.model_sha, self.backend, self.fixture_override = model_sha, backend, fixture_context_override

        class Observer(NativeMeter):
            def __init__(self):
                super().__init__()
                self.lock, self.finished = threading.RLock(), False

            def spawn(self, argv, **kwargs):
                with self.lock:
                    if self.finished:
                        raise RuntimeError("Native observer is closed")
                    if fixture_context_override:
                        argv = [*argv, "--override-kv", "llama.context_length=int:4096"]
                    return super().spawn(argv, **kwargs)

            def finish(self):
                with self.lock:
                    if self.finished:
                        return self.exits
                    self.finished = True
                    deadline = time.monotonic()+3
                    self.exits = []
                    for handle in self.handles:
                        try:
                            remaining = max(0, int((deadline-time.monotonic())*1000))
                            self.exits.append(self.kernel.WaitForSingleObject(handle, remaining) == 0)
                        finally:
                            self.kernel.CloseHandle(handle)
                    return self.exits

        self.meter = Observer()
        owner = self

        class ObservedClient(LoopbackClient):
            def request_json(self, path, **kwargs):
                result = super().request_json(path, **kwargs)
                if path == "/tokenize" and kwargs.get("payload", {}).get("content") and owner._fault_requested:
                    self.owned_manager._process.terminate()
                    owner._fault_injected = True
                return result

            @contextmanager
            def response_bytes(self, path, **kwargs):
                with super().response_bytes(path, **kwargs) as chunks:
                    def observed():
                        for chunk in chunks:
                            if path == "/v1/chat/completions":
                                owner._tap.feed(chunk)
                            yield chunk
                    yield observed()

        def manager_factory(config):
            def client_factory(port, key):
                client = ObservedClient(port, key)
                client.owned_manager = manager
                return client
            manager = SidecarManager(config, resolver=lambda _name: runtime_dir,
                process_factory=self.meter.spawn, client_factory=client_factory,
                device_selector=lambda *args, **kwargs: select_device(*args, **kwargs,
                    process_factory=self.meter.spawn))
            self.managers.append(manager)
            return manager

        self.config = LocalLLMConfig(enabled=True, model_path=str(model), backend=backend,
            n_threads=1, max_tokens=1, prepare_prompt=False)
        # Device selection is part of the explicit developer recipe, not an app preference edit.
        if device is not None:
            from dataclasses import replace
            base_factory = manager_factory
            def manager_factory(config):
                return base_factory(replace(config, device=device))
        self.manager_factory, self.cleaner_factory = manager_factory, LocalLLMCleaner
        cleaner = DictationPipeline(DictationConfig(llm=self.config),
            llm_cleaner=LocalLLMCleaner(self.config, manager_factory=manager_factory))
        cleaner.glossary = Glossary(user_terms=("Saydraft",))
        baseline = DictationPipeline(DictationConfig())
        baseline.glossary = cleaner.glossary
        self.expected = baseline.process_transcript("um send 2 files to Saydraft", DictationContext())
        try:
            super().__init__(cleaner=cleaner, history_path=output/"history.db",
                raw_factory=lambda _index: "um send 2 files to Saydraft")
        except BaseException:
            self.close()
            raise

    def warmup(self):
        super().warmup()
        self.prepare(1)

    def prepare(self, index):
        if self._prepared_index == index:
            return
        if index > 1 and index % 2 == 1:
            self.pipeline.close()
            self.pipeline.llm = self.cleaner_factory(self.config, manager_factory=self.manager_factory)
        self._fault_requested, self._fault_injected = index % 2 == 0, False
        self._tap = StreamEvidence()
        self.pipeline.warm()
        manager = self.managers[-1]
        deadline = time.monotonic()+20
        while not manager.ready and time.monotonic() < deadline:
            manager.prepare()
            time.sleep(.01)
        if not manager.ready:
            self.preparation_failure = dict(manager.status)
            raise RuntimeError("Owned native cleanup did not become ready")
        self._prepared_index = index

    def __call__(self, index):
        started = time.monotonic()
        super().__call__(index)
        decision = self.pipeline.last_llm_decision
        row = {"cycle": index, "termination_after_tokenization": self._fault_requested,
            "termination_observed": self._fault_injected, "decision": decision,
            "release_seconds": time.monotonic()-started, "native_stream_complete": self._tap.complete,
            "rules_preserved": self.worker.last_result.cleaned_text == self.expected,
            "clipboard_restored": self.clipboard.paste() == "clipboard sentinel"}
        self.cycles.append(row)
        with (self.output/"cycles.jsonl").open("a", encoding="utf-8") as journal:
            journal.write(json.dumps(row, allow_nan=False)+"\n")
        allowed = {"unavailable", "timeout"} if self._fault_requested else {"incomplete", "timeout"}
        if (not row["rules_preserved"] or decision not in allowed
                or self._fault_requested and not self._fault_injected
                or decision == "incomplete" and not self._tap.complete):
            raise RuntimeError("Native cleanup evidence did not match the requested cycle")

    def close(self):
        if self._native_closed:
            return
        self._native_closed = True
        try:
            super().close()
        except Exception as error:
            self._native_close_errors.append(type(error).__name__)
        for manager in self.managers:
            try:
                manager.close()
            except Exception as error:
                self._native_close_errors.append(type(error).__name__)
        self._native_exits = self.meter.finish()
        if self._native_close_errors or not self._native_exits or not all(self._native_exits):
            raise RuntimeError("Native shutdown could not be verified")

    def details(self):
        from saydraft.models.runtime_ids import runtime_model_id
        details = super().details()
        normal = sum(row["native_stream_complete"] and not row["termination_after_tokenization"] for row in self.cycles)
        verified = bool(self._native_exits) and all(self._native_exits) and not self._native_close_errors
        strict_cycles = all(row["rules_preserved"] and row["clipboard_restored"]
            and row["termination_after_tokenization"] == row["termination_observed"]
            and (row["decision"] != "incomplete" or row["native_stream_complete"]) for row in self.cycles)
        details.update(native_cleanup_exercised=bool(self.meter.handles),
            scope="owned native cleanup; synthetic capture/ASR/focus; real SQLite and Inserter; memory keyboard/clipboard",
            native_processes_started=len(self.meter.handles), native_exit_observed=list(self._native_exits),
            native_shutdown_complete=verified, normal_length_limited_streams_checked=normal,
            native_close_errors=list(self._native_close_errors), cycles=list(self.cycles),
            model_sha256=self.model_sha, fixture_context_override=self.fixture_override, backend=self.backend,
            runtime_id=runtime_model_id(self.backend),
            selected_device=self.managers[-1].selected_device if self.managers else None,
            recipe={"threads": 1, "context_size": 4096, "max_output_tokens": 1, "temperature": 0,
                "cleanup_timeout_ms": 800, "interactive_prompt_preparation": False, "interactive_budget_gate": False},
            preparation_failure=self.preparation_failure,
            quality_claim=False, outcomes_passed=expected_outcomes(self.cycles),
            checks_passed=(details["checks_passed"] and verified and normal > 0 and strict_cycles
                and expected_outcomes(self.cycles) and len(self.cycles) == self.attempts))
        return details
