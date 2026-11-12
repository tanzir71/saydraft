"""Process-wide admission: observe old process exit before admitting a new one."""

import logging
import threading

logger = logging.getLogger(__name__)


class ProcessSlotBusy(RuntimeError):
    pass


class _ProbeLease:
    def __init__(self, slot, process):
        self.slot, self.process = slot, process

    def __enter__(self):
        return self.process

    def __exit__(self, *_args):
        self.slot.retire(self.process)


class ProcessSlot:
    def __init__(self, *, timer_factory=threading.Timer):
        self._lock = threading.RLock()
        self._process = self._reaper = None
        self._timer = timer_factory

    def _release_exited(self):
        if self._process is None:
            return True
        if self._process.poll() is None:
            return False
        self._process.close()
        self._process = None
        if self._reaper is not None:
            self._reaper.cancel()
            self._reaper = None
        return True

    def start(self, factory, argv, *, env):
        with self._lock:
            if not self._release_exited():
                return None
            process = factory(argv, env=env)
            self._process = process
            return process

    def start_probe(self, factory, argv, *, env, **options):
        process = self.start(lambda values, *, env: factory(values, env=env, **options), argv, env=env)
        if process is None:
            raise ProcessSlotBusy("Another native cleanup process is active")
        return _ProbeLease(self, process)

    def retire(self, process):
        with self._lock:
            if process is not self._process:
                return True  # Already reaped; an old manager cannot touch the new owner.
            try:
                process.terminate()
                return self._release_exited()
            finally:
                if self._process is not None and self._reaper is None:
                    self._schedule_reap(process)

    def _schedule_reap(self, process):
        def reap():
            with self._lock:
                if process is not self._process:
                    return
                self._reaper = None
                try:
                    if self._release_exited():
                        return
                except Exception:
                    # Fail closed: retain the job/process handles and refuse a new child.
                    logger.warning("Local cleanup exit observation failed")
                self._schedule_reap(process)

        self._reaper = self._timer(0.05, reap)
        self._reaper.daemon = True
        self._reaper.start()


# Shared by every application cleaner, including settings/service replacements.
PROCESS_SLOT = ProcessSlot()
