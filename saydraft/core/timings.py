"""Timing reports contain stage metadata, never transcript content."""

import logging

logger = logging.getLogger(__name__)
STAGES = ("record", "audio", "vad", "stt", "lid", "dictionary", "rules", "llm", "insert")


class TimingReporter:
    def __init__(self, *, notify=lambda message: None, llm_enabled=False):
        self.notify = notify
        self.llm_enabled = llm_enabled
        self._suggested_base = False

    def report(self, timings: dict, model: str):
        values = {stage: float(timings.get(stage, 0) or 0) for stage in STAGES}
        total = sum(value for stage, value in values.items() if stage != "record")
        logger.info("Dictation timings: %s total=%.3fs model=%s",
                    " ".join(f"{stage}={value:.3f}s" for stage, value in values.items()), total, model)
        if "background_stt" in timings:
            logger.info("Recognition completed during capture: background_stt=%.3fs", timings["background_stt"])
        if model in ("small", "whisper-small") and total > (3.0 if self.llm_enabled else 1.5) and not self._suggested_base:
            self._suggested_base = True
            self.notify("Small model is running slowly; try the base model in Settings > Models.")
