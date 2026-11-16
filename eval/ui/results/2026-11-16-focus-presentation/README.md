# Keyboard-only focus indicators · 16 November 2026

Runtime source: `b6322666fc1cee11c06492ab493d9e4d74b3511b`.
QA: `D:/Saydraft-Codex-QA-20261112-01a1cbc7/focus-presentation-20261116-r1`.

Unsigned portable:
`D:/Saydraft-Codex-QA-20261112-01a1cbc7/focus-presentation-package-20261116-r1/artifacts/Saydraft-0.1.0-win-x64.zip`.
Size: 157,355,451 bytes. SHA-256:
`0891f00001bf71a26b15fcb527310521846408da52c20dc14f910471ef48e3eb`.
The clean-source build exits zero; frozen runtime/resources/notices pass.
Independent checks verify all 1,439 actual disk/ZIP payloads, 84 embedded modules
and both generated focus stylesheets against Git. Installer/signing/release gates
remain false for this portable-only delivery.

Mouse/touch interaction no longer leaves the branded focus ring on action
buttons, toggles, segments or sidebar navigation. Keyboard interaction restores
the indicator, including after clicking the already focused control. Actual
focus policies, activation signals and editable-field focus are unchanged.
High contrast retains the native stylesheet. The custom toggle/sidebar painting
uses the same input-modality state as the generated light/dark stylesheets.

| Check | Result |
| --- | --- |
| Theme and focus regression selection | 46 passed, including ten light/dark control scenarios and mouse → Tab → same-control mouse → keyboard activation |
| Existing Hub keyboard integration | 13 passed; 8 unrelated cases deselected; forward/reverse Tab, 16/32px, light/dark/high contrast and multiline editor navigation |
| Fresh 1×/2× gallery snapshot comparison | 2 passed; no baseline edits |
| Generated token outputs and Ruff | Passed |

The tests send Qt events only to owned offscreen widgets. File/worker guards
report no owner profile, device enumeration, microphone, clipboard or native
input access and no blocked/unexpected port attempts. Public screenshot pairs
are cropped directly from the final font-loaded control tests. They demonstrate
the absence of a mouse ring and presence of a keyboard cue; platform focus
painting remains platform-dependent. Earlier fixture failures are retained: the
tool button's native default uses Tab focus, and the standalone navigation
fixture initially lacked the app's selected Home row. No product code was changed
to bypass those assertions; the fixtures were aligned with the cases being tested.

No new host acceptance was run. Earlier insertion/audio acceptance limits remain
in the [delivery handover](../../../../docs/DELIVERY_HANDOVER.md).
