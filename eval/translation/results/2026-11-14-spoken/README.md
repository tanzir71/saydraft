# Spoken translation verification · 2026-11-14

Implementation is connected through the normal worker and independent Labs/Style
controls. Final clean-source CI/package checks and retained evidence are pending.
This checkpoint does not check off P7.2 yet.

Pre-commit native diagnostics use authored text and the actual pinned 4B model,
exclusive owner and translation wrapper. All eight EN↔ES/EN↔AR smoke cases passed.
The first extra prose case needed a reference correction: Spanish naturally
translates unquoted YES to SÍ. A separate literal-code case then exposed a genuine
`code_changed` refusal, safely blocking the candidate. Fresh opaque code slots,
validated before one-pass restoration, fixed that case. The third diagnostic
passed all 10 cases, with unchanged source/pins and both native exits observed.
These original reports will be retained alongside the final clean-source run.

Controlled worker tests separately cover temporary History before simulated
paste, raw recovery, cancellation, source-review handling, missing models,
settings and shared runtime resolution. Offscreen renders cover both themes at
1x/2x. Neither test scope establishes physical microphone/hotkeys/clipboard/input,
broad semantic quality, owner speech accuracy or release latency.

See [setup, behavior and limits](../../../../docs/TRANSLATE.md).
