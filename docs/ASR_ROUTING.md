# Speech model routing

Fresh profiles use automatic model choice. Settings → Languages offers Auto or
up to three pins. English-only plus English max selects Parakeet v2; pins wholly
inside Parakeet's 25-language set select v3. Any other combination selects the
shared optional Whisper turbo model. A single Whisper language pin is passed to
the decoder; multiple pins leave its language detection enabled.

Selecting languages never downloads models. Bengali and Arabic share the same
All languages download, initiated on the Models tab. A missing selected model
produces a Settings error before the microphone opens. Choosing a model manually
turns automatic routing off. Existing profiles retain their manual model choice
until routing is explicitly enabled. Setup preserves the fresh-profile default
unless a different model is selected.

Per-app-group model overrides are supported in config JSON, for example:

```json
{"stt": {"app_model_overrides": [
  {"app_group": "terminal", "model_id": "whisper-small"}
]}}
```

Overrides take priority over pins. They use the captured foreground app group;
the more detailed Windows classifier and Hub editor are later roadmap tasks.
Only catalogued ASR model IDs and safe group names survive config sanitization.

## Automatic retry policy and limits

Auto starts with Parakeet v3. Empty output, very short output for long voiced
audio, an unsupported script, or a reported language outside its supported set
can request a multilingual retry. Greek and Cyrillic are valid Parakeet scripts
and are not rejected merely for being non-Latin.

An automatic retry requires the optional model to be installed and already warm,
with an observed recognition time. The conservative estimate plus primary time
must fit the configured `fallback_budget_ms` (800 ms by default). Unknown timing
or a cold model requests manual retry instead. Failed/empty fallback output keeps
the primary transcript. This is a prediction gate; native inference cannot be
interrupted at a strict wall-clock deadline. History retry with retained audio is
being implemented separately before P3.4 is checked off.

At most two model instances are cached. A changed Whisper language hint reuses its
weights. Eviction removes that model's timing estimate. Session history records
all engines used, joined with ` + ` when background segments used multiple models.
The selected model and actual recognized language are tracked separately.

**Language-ID limitation:** the pinned Parakeet runtime returned no language ID
for the real English fixture. Its implicit multilingual recognition does not
provide the explicit audio language-ID signal assumed in the original plan.
The router accepts such evidence when available, but current Auto decisions rely
on transcript checks. Fluent hallucinations in a supported script can evade them.
Pin Bengali/Arabic (or select All languages) for reliable model selection; no
extra language-ID model is downloaded silently.

## Verification, 2026-11-12

Unit checks cover routing priorities, mixed pins, English max, every fallback gate,
valid Greek/Cyrillic output, failure preservation, model-cache eviction, migrations
and explicit-download behavior. The full suite passes 397 tests with five native
checks skipped; cleanup evaluation remains 42/42.

Real routed inference then ran under NetworkGuard using verified QA artifacts:

| Pin | Engine | Reported language | Recognition time |
|---|---|---|---:|
| English | Parakeet v3 | Unavailable | 0.264 s |
| Bengali | Whisper turbo | `bn` | 13.213 s |
| Arabic | Same cached Whisper turbo | `ar` | 11.894 s |

All produced nonempty text; the Bengali/Arabic output used the correct scripts.
Only two engines were cached, and the Arabic language switch reused loaded
Whisper weights. Initial preparation was 4.012 s for Parakeet and 23.191 s for
Whisper in this routed process using relocated QA files; those are not parity
latency results. Owner accuracy acceptance remains deferred.
