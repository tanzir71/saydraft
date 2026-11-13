"""Owned worker/persistence/insertion fixtures shared by soak entry points."""

from __future__ import annotations

import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace


class MemoryClipboard:
    def __init__(self):
        self.value = ""

    def paste(self):
        return self.value

    def copy(self, text):
        self.value = str(text)


class MemoryKeyboard:
    def __init__(self, before_send=lambda _hotkey: None):
        self.sent, self.written = [], []
        self.before_send = before_send

    def send(self, hotkey):
        self.before_send(hotkey)
        self.sent.append(str(hotkey))

    def write(self, text):
        self.written.append(str(text))


class InlineExecutor:
    def submit(self, callback, *args):
        callback(*args)

    def shutdown(self, **_kwargs):
        pass


class InactiveTimer:
    def __init__(self, *_args):
        pass

    def start(self):
        pass

    def cancel(self):
        pass


class SyntheticCycleRunner:
    """Real services with explicit fake capture, ASR, focus, keyboard and clipboard."""

    fail_fast = False

    def __init__(self, *, cleaner=None, history_path=None, raw_factory=None):
        from saydraft.config import default_config
        from saydraft.core.container import Services
        from saydraft.core.interfaces import TargetContext
        from saydraft.core.processing import IdentityFormatter, TranscriptProcessor
        from saydraft.core.session import DictationSession
        from saydraft.core.worker import SessionWorker
        from saydraft.dictation import DictationConfig, DictationPipeline
        from saydraft.history import DictationHistoryStore
        from saydraft.insert.inserter import Inserter

        self._closed = False
        self._temp, self.worker, self.pipeline = None, None, cleaner
        self._clock, self._raw = 0.0, ""
        self.attempts = self.insertions = self.clipboard_failures = 0
        self.history_rows = None
        self.close_errors = []
        self.raw_factory = raw_factory or (lambda i: f"um soak cycle {i} item one item two")
        try:
            if history_path is None:
                self._temp = tempfile.TemporaryDirectory(prefix="saydraft-soak-")
                history_path = Path(self._temp.name)/"history.db"
            self.history_path = Path(history_path).resolve()
            self.pipeline = cleaner if cleaner is not None else DictationPipeline(DictationConfig())
            self.history = DictationHistoryStore(self.history_path)
            self.clipboard = MemoryClipboard()
            self.clipboard.copy("clipboard sentinel")
            self.keyboard = MemoryKeyboard(self._before_paste)
            self.inserter = Inserter(clipboard=self.clipboard, keyboard=self.keyboard,
                focus_provider=lambda: "notepad", sleep=lambda _seconds: None)
            formatter = IdentityFormatter()
            processor = TranscriptProcessor(cleaner=self.pipeline, formatter=formatter,
                history=self.history, inserter=self.inserter)
            services = Services(default_config(),
                SimpleNamespace(start=lambda: None, stop=lambda: [0.1]),
                SimpleNamespace(transcribe=lambda _audio: self._raw), self.pipeline,
                formatter, self.inserter,
                SimpleNamespace(capture=lambda: TargetContext("notepad", "Notepad")),
                self.history, processor, [])
            self.worker = SessionWorker(services, executor=InlineExecutor(), timer_factory=InactiveTimer,
                session=DictationSession(clock=lambda: self._clock))
        except BaseException:
            self.close()
            raise

    def warmup(self):
        # Schema and initial service preparation precede the explicit RSS baseline.
        if self._closed or self.history.list_recent(limit=1):
            raise RuntimeError("Soak requires an open runner and fresh private History")

    def _before_paste(self, hotkey):
        if hotkey != "ctrl+v":
            raise RuntimeError("Unexpected simulated keyboard action")
        latest = self.history.list_recent(limit=1)
        if (not latest or latest[0].id != self.attempts or latest[0].raw_text != self._raw
                or latest[0].cleaned_text != self.clipboard.paste()):
            raise RuntimeError("History must contain this result before paste")
        self.insertions += 1

    def __call__(self, index):
        if self._closed:
            raise RuntimeError("Soak runner is closed")
        self.attempts += 1
        self._raw = self.raw_factory(index)
        try:
            if not self.worker.start_recording():
                raise RuntimeError("Session remained busy")
            self._clock += 1.0
            self.worker.stop_recording()
            result = self.worker.last_result
            if (result is None or result.insertion.status != "inserted"
                    or self.insertions != self.attempts or self.keyboard.written):
                raise RuntimeError("Session failed checked clipboard delivery")
        finally:
            if self.clipboard.paste() != "clipboard sentinel":
                self.clipboard_failures += 1
        if self.clipboard_failures:
            raise RuntimeError("Simulated clipboard was not restored")

    def _count_history(self):
        with closing(sqlite3.connect(self.history_path.as_uri()+"?mode=ro", uri=True)) as connection:
            return connection.execute("SELECT COUNT(*) FROM dictations").fetchone()[0]

    def close(self):
        if self._closed:
            return
        self._closed = True
        for phase, callback in (
            ("history", lambda: setattr(self, "history_rows", self._count_history())),
            ("worker", lambda: self.worker.shutdown() if self.worker is not None else None),
            ("pipeline", lambda: self.pipeline.close() if self.pipeline is not None else None),
            ("temporary_files", lambda: self._temp.cleanup() if self._temp is not None else None),
        ):
            try:
                callback()
            except Exception as error:
                self.close_errors.append({"phase": phase, "error_type": type(error).__name__})
        if self.close_errors:
            raise RuntimeError("Soak runner teardown failed")

    def details(self):
        restored = self.clipboard.paste() == "clipboard sentinel"
        return {"scope": "synthetic capture/ASR/focus; real SessionWorker, SQLite and Inserter; memory keyboard/clipboard",
            "clipboard_scope": "memory", "os_clipboard_used": False, "os_input_used": False,
            "microphone_used": False, "native_cleanup_exercised": False,
            "attempted_cycles": self.attempts, "history_rows": self.history_rows,
            "checked_insertions": self.insertions, "clipboard_failures": self.clipboard_failures,
            "simulated_paste_events": len(self.keyboard.sent), "simulated_typing_events": len(self.keyboard.written),
            "clipboard_restored": restored, "close_errors": list(self.close_errors),
            "checks_passed": (self._closed and not self.close_errors and restored
                and self.clipboard_failures == 0 and self.history_rows == self.insertions == self.attempts
                and len(self.keyboard.sent) == self.insertions and not self.keyboard.written)}

    def __del__(self):
        # Only our TemporaryDirectory is removed; retained native QA output is never deleted.
        if getattr(self, "_temp", None) is not None:
            self._temp.cleanup()
