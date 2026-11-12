"""Clock-driven Bar motion. No microphone, Qt timer or desktop dependency."""

from __future__ import annotations

import math


class RmsEnvelope:
    """A one-pole RMS envelope with 30 ms attack and 120 ms release."""

    # Fixed spatial weights make all fourteen bars move with actual volume.
    WEIGHTS = (.36, .52, .74, .46, .82, .63, 1., .71, .89, .57, .78, .48, .65, .39)

    def __init__(self, now: float = 0):
        self.reset(now)

    def reset(self, now: float) -> None:
        self.level = self.target = 0.0
        self.updated_at = now

    def advance(self, now: float) -> float:
        elapsed = max(0., now - self.updated_at)
        self.updated_at = max(self.updated_at, now)
        tau = .030 if self.target > self.level else .120
        self.level += (self.target - self.level) * -math.expm1(-elapsed / tau)
        return self.level

    def sample(self, rms: float, now: float) -> None:
        self.advance(now)
        value = float(rms)
        self.target = max(0., min(1., value * 8)) if math.isfinite(value) else 0.

    @property
    def heights(self) -> tuple[float, ...]:
        return tuple(3 + 19 * self.level * weight for weight in self.WEIGHTS)


def shimmer_opacity(index: int, seconds: float) -> float:
    """A slow left-to-right opacity sweep; the bar geometry never changes."""
    position = (seconds % 2.4) / 2.4 * 20 - 3
    return .48 + .52 * math.exp(-((index - position) / 3.2) ** 2)


def insertion_message(reason: str, *, saved: bool, paste_hint: str) -> tuple[str, str]:
    """Public delivery copy. A failed History write must never claim 'Saved'."""
    title = {
        "focus_changed": "Focus changed", "password_field": "Password field",
        "target_elevated": "Admin window", "field_unavailable": "Field unavailable",
        "modifier_held": "Shortcut still held", "clipboard_changed": "Clipboard changed",
        "insertion_unconfirmed": "Check the target", "history_unavailable": "History unavailable",
        "cancelled": "Dictation cancelled", "saved_only": "Saved to History",
        "review_only": "Review in History",
    }.get(reason, "Couldn’t insert")
    if not saved:
        return title, "Not saved · words kept in this session"
    if reason == "insertion_unconfirmed":
        return title, "Saved · check for pasted text before pasting again"
    if not paste_hint.strip():
        return title, "Saved · open History to copy"
    return title, f"Saved, press {paste_hint} to paste"
