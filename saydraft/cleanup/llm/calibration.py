"""Measure the owned live decoder using fixed text and bounded native requests."""

import math
import statistics
import threading
from dataclasses import dataclass

_PROMPT = "Continue with a short description of a quiet garden."


@dataclass(frozen=True)
class DecodeMeasurement:
    generation: int
    rates: tuple[float, float, float]

    def metadata(self):
        return {"generation": self.generation, "tokens_per_sample": 60, "sample_count": 3,
                "tokens_per_second": list(self.rates), "median_tps": statistics.median(self.rates),
                "conservative_tps": min(self.rates)}


class DecoderCalibration:
    def __init__(self, manager):
        self.manager, self._lock = manager, threading.Lock()
        self._measurement = self._failed = None

    @property
    def current(self):
        generation = self.manager.generation
        with self._lock:
            return self._measurement if (generation is not None and self._measurement is not None
                                         and self._measurement.generation == generation) else None

    def measure(self, *, timeout=60):
        generation = self.manager.generation
        if type(generation) is not int or generation <= 0:
            return "not_ready"
        if self.current is not None:
            return "calibrated"
        with self._lock:
            if self._failed == generation:
                return "decoder_calibration_invalid"

        def operation(client, deadline):
            rates = []
            for _ in range(3):
                value = client.request_json("/completion", payload={"prompt": _PROMPT, "n_predict": 60,
                    "temperature": 0, "ignore_eos": True, "cache_prompt": False}, deadline=deadline)
                timings = value.get("timings", {})
                if not isinstance(timings, dict):
                    return {"invalid": True}
                count, rate = timings.get("predicted_n"), timings.get("predicted_per_second")
                if (type(count) is not int or count != 60 or type(rate) not in (int, float)
                        or not math.isfinite(rate) or rate <= 0):
                    return {"invalid": True}
                rates.append(float(rate))
            return {"rates": rates}  # Generated prose never leaves this operation.

        reply = self.manager.run(operation, timeout=timeout)
        if reply.reason != "ok":
            return reply.reason
        if self.manager.generation != generation:
            return "instance_changed"
        with self._lock:
            if not reply.value or reply.value.get("invalid"):
                self._measurement, self._failed = None, generation
                return "decoder_calibration_invalid"
            self._measurement = DecodeMeasurement(generation, tuple(reply.value["rates"]))
            self._failed = None
        return "calibrated"
