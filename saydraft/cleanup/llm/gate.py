"""Metadata-only need and latency decisions; rejected calls retain rules."""

import math
import re
from dataclasses import dataclass

from .validate import extract_words

_BACKTRACK = re.compile(r"\b(?:actually|scratch\s+that|never\s+mind|no\s+wait)\b", re.I)
_LIST = re.compile(r"\b(?:new\s+(?:line|paragraph)|(?:bullet|numbered)\s+list|next\s+item)\b", re.I)
_FILLER = re.compile(r"\b(?:um|uh|erm|you\s+know|i\s+mean)\b", re.I)
PREDICTION_HEADROOM = 2.0  # Native CPU replies exceeded the raw estimate by up to 1.60x.
MIN_REQUEST_SECONDS = .05  # Decline tiny RPC windows after the separate 50 ms delivery reserve.


@dataclass(frozen=True)
class NeedScore:
    score: int
    reasons: tuple[str, ...]


def score_need(text, *, style="neutral", intensity=3):
    words = len(extract_words(text))
    cues = [("backtrack", 2, bool(_BACKTRACK.search(text))),
            ("list", 2, bool(_LIST.search(text))),
            ("fillers", 2, len(_FILLER.findall(text)) / max(1, words) >= .15),
            ("long", 2, words > 25), ("style", 1, style != "neutral"),
            ("polished", 2, intensity == 4)]
    return NeedScore(sum(weight for _, weight, present in cues if present),
                     tuple(name for name, _, present in cues if present))


def request_timeout(timeout_ms, *, now, deadline=None):
    if not math.isfinite(now) or type(timeout_ms) is not int or timeout_ms <= 0:
        return 0.0
    available = timeout_ms / 1000
    if deadline is not None:
        if type(deadline) not in (int, float) or not math.isfinite(deadline):
            return 0.0
        available = min(available, deadline - now)
    return max(0.0, available - .05)


def decision(need, reason, *, remaining, predicted=None, source_tokens=0, pending_tokens=0):
    milliseconds = predicted * 1000 if predicted is not None else None
    return {"reason": reason, "need_score": need.score, "need_reasons": list(need.reasons),
            "remaining_ms": max(0.0, remaining) * 1000,
            "predicted_ms": milliseconds if milliseconds is not None and math.isfinite(milliseconds) else None,
            "source_tokens": source_tokens, "pending_tokens": pending_tokens}


def predict(need, *, source_tokens, pending_tokens, output_limit, rate, remaining):
    if rate is None or not math.isfinite(rate) or rate <= 0:
        return decision(need, "skip_calibration", remaining=remaining)
    if source_tokens <= 0:
        return decision(need, "skip_tokenization", remaining=remaining)
    # Expected output differs from the larger safety cap. Prefill assumes 4x the
    # decode rate; uniform headroom covers observed underprediction, not a guarantee.
    output = min(output_limit, math.ceil(source_tokens * 1.25) + 2)
    predicted = PREDICTION_HEADROOM * (pending_tokens / (rate * 4) + output / rate)
    return decision(need, "call" if predicted <= remaining else "skip_budget", remaining=remaining,
                    predicted=predicted, source_tokens=source_tokens, pending_tokens=pending_tokens)
