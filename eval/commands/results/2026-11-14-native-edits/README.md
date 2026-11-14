# Native command-edit generation, 14 November 2026

At clean `7265787`, the cached Qwen3.5 **4B Q4_K_M** model passes all **30/30**
authored cases through the real pinned llama.cpp **b12110 Vulkan** sidecar. The
same source and corpus with **2B Q4_K_M** passes **29/30** anchor checks. The
4B outputs were also reviewed for the requested transformation and retained
facts/actions. This establishes a narrow generation regression check. **P7.1 is
still open:** Labs/Pro admission, hold recording, copy fallback, native replacement
confirmation and standalone Scratchpad Copy recovery are not connected.

| Record | Source | Model | Completed streams | Authored checks |
|---|---|---|---:|---:|
| [Endpoint diagnostic](01-endpoint-refusal/report.json) | `fbf91dd` | 2B | 0/30 | 0/30 |
| [Initial schema prompt](02-schema-2b/report.json) | `4d8309a` | 2B | 30/30 | 17/30 |
| [Transformation examples](03-transform-2b/report.json) | `21c1f6c` | 2B | 30/30 | 24/30 |
| [Qualifiers and actions](04-qualifiers-2b/report.json) | `647061f` | 2B | 30/30 | 29/30 |
| [Same prompt comparison](05-qualifiers-4b/report.json) | `647061f` | 4B | 30/30 | 29/30 |
| [Ordinal-preserving example](06-ordinal-4b/report.json) | `7265787` | 4B | 30/30 | 30/30 |
| [Same final prompt comparison](07-ordinal-2b/report.json) | `7265787` | 2B | 30/30 | 29/30 |

The first attempt reached no inference: `/apply-template` was missing from the
loopback endpoint allowlist. Its legacy `complete: true` means all requests were
attempted, with process cleanup; it is **not** a completed generation run. The
fixed probe records individual `stream_complete` facts and requires every stream
for generation completeness. No failed row or run was removed.

The 4B comparison initially refused a valid bullet conversion that removed the
leading ordinal “First.” The final prompt demonstrates preserving the ordinal;
the number-preservation validator was not relaxed. The evaluation corpus and its
anchors remain byte-identical across all seven runs. Prompt refinement used this
authored set; these are not blind or unseen-data measurements.

The final 2B `formal-05` output uses “inquire with Maya,” which misses the narrow
contact-word anchor. That miss alone is not proof of incorrect meaning. Separate
review found that `formal-06` loses the conditional request to report issues back,
and `formal-08` changes a future promise to a general statement. Both pass the
mechanical and anchor checks. The validator is not a semantic oracle, and 2B
general editing quality remains unaccepted. No app default or model choice was
changed as a result of this comparison.

Each request uses authored selected text and a scripted instruction, a 45-second
deadline, a 4,096-token context, a 768-token output cap and temperature zero. The
model's rendered chat is counted first, with the full output allowance plus a
64-token reserve. The probe installs the Python NetworkGuard, uses only the owned
authenticated loopback transport and runs one local native measurement at a time
on the RTX 3060 (`Vulkan1`). Startup is separate. Timings include template/token
requests and generation; they are **not** release-to-paste or tier acceptance.

The [index](index.json) hashes all 14 unchanged report/journal payloads. An
independent audit confirms every journal equals its report, all 210 attempts are
retained, all 180 completed generations have native exit receipts, every weight
hash matches the pinned candidate catalog, and source/model/runtime hashes did
not change during each run. The latest source fingerprints were independently
rechecked. The 4B weights/card/license and runtime received full pinned hash
verification. Two native exit receipts per run cover device inspection and the
server. No owner microphone, playback, clipboard, foreground, hotkeys or OS text
input was used.

The separate processing tests exercise actual temporary SQLite History with
memory input/clipboard and injected selection/session checks: history before
paste, changed/read-only/sensitive/expired targets, cancellation, storage failure,
typing-profile refusal, clipboard-error refusal, restored memory clipboard and
dictation stats. These are not native selection/paste or full app integration.
The previous native selected-range proof remains in the
[selection record](../../../context/results/2026-11-14-selection/README.md).
See [Command Mode status](../../../../docs/COMMAND_MODE.md) for remaining work.
