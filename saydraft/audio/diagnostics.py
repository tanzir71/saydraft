"""Actionable input hints; level checks never claim speech recognition."""

import math


def input_signal_hint(audio, *, quiet_threshold=.003):
    import numpy as np

    values = np.asarray(audio)
    if not values.size:
        return "No audio arrived. Open Settings → Microphone, choose your microphone and use Test input."
    peak = max(abs(float(np.min(values))), abs(float(np.max(values))))
    if not math.isfinite(peak):
        return "The input returned invalid audio. Check Settings → Microphone and use Test input."
    if peak <= .000001:
        return ("No sound reached Saydraft. Open Settings → Microphone, choose your microphone "
                "rather than an unused virtual input, and use Test input.")
    if peak < quiet_threshold * 2:
        return "The microphone is very quiet. Check its input volume or Whisper mode in Settings → Microphone."
    return None
