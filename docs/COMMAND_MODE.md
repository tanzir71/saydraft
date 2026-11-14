# Command Mode implementation

P7.1 remains in progress. The selected-target boundary, explicit local edit
client/validator and guarded processing boundary, including bounded post-write
confirmation, and independent Copy recovery windows are implemented. The shortcut/Labs
and model admission, clipboard-copy fallback and instruction recording still need
connecting to those boundaries. No Command Mode control is advertised as
available in the app.

## Local edit and delivery boundaries

`LocalLLMCleaner.edit_selection()` reuses the installed, serial sidecar. It has
an explicit 45-second editing deadline, separate from the normal 800-ms cleanup
budget. Cold/busy/unavailable requests return their state, without substituting
the spoken instruction. No model download or speech-language setting is changed.
The request contains the complete bounded selection and instruction, with no
surrounding document. The pinned server's rendered template is tokenized before
generation; the full output allowance plus a 64-token reserve must fit the
configured context. Oversized input is refused rather than truncated.
Literal model-role delimiters and XML-style tags in the document/instruction are
JSON-escaped before rendering the native chat template; decoding the data restores
the complete original text. This encoding boundary alone is not proof of general
prompt-injection resistance. Six separate authored untrusted-document cases
exercise questions, imperative text, native role tags, XML and nested JSON.

The response uses a one-field JSON schema. Delivery requires a complete SSE
finish, exactly one `replacement` string, and no tools, duplicate/extra fields,
invalid controls or new response wrappers. The independent edit validator allows
rewriting, while preserving numeric values, currencies, URLs, emails, code
literals and placeholders. Ordinary edits also retain negation and explicit
date/time/number-word facts. The ambiguous word “May” is ignored only in clear
auxiliary phrases such as “may be”; calendar uses remain protected. An explicit English translation instruction permits
language and word changes. Conservative checks can reject legitimate edits;
they do not prove factual or semantic equivalence. The normal cleanup validator
and its word-preservation rules are unchanged.

An edit evicts both the native cleanup prefix receipt and background readiness.
An in-flight preparation cannot publish a stale ready state after invalidation;
ordinary cleanup must prepare again. Cancellation discards the candidate at
request boundaries and during streaming. A blocked HTTP read is still bounded
by the request deadline; this boundary does not promise instantaneous native
inference interruption.

`CommandEditProcessor` receives an already admitted current session and selection
lease. It validates the target before generation, saves selected text, replacement,
instruction/model provenance and timings before input, and supplies the current
session plus exact selection guard immediately before paste. Its `paste_only`
insertion option refuses typing profiles and clipboard-error typing fallback.
The processor uses the capture provider's actual `ready` selection contract;
an earlier `ok`/`ready` mismatch is corrected and covered through the real provider
and bounded owner, rather than only a manually constructed snapshot.

After paste, success requires fresh target/password metadata, a collapsed caret
and two exact reads of the intended replacement span. Capture retains a native
text-unit offset whose metadata-only round trip reaches the original start;
confirmation reconstructs that position without treating Python character counts
as native coordinates. The span reads are capped at the expected replacement's
UTF-16 size plus one overflow unit, never a full-document `GetText`. A provider
that cannot supply this position, a changed/unsupported field, a partial write or
an ignored paste yields `insertion_unconfirmed`. The native selection lease is
one-shot and retired after confirmation. This remains an observation, not an
atomic lock against concurrent application changes.

An unconfirmed paste may already have written text. Recovery must say to check
the original field before copying/pasting again; there is no automatic retry.
Failed delivery passes a standalone recovery result to the caller. The app's
queued Qt bridge accepts generation/ticket-tagged recovery requests. Each accepted
request opens an independent editable Scratchpad with Copy and the existing
revision-aware autosave/retry flow. Its note store always uses `activate=False`:
the active note pointer and any dirty or conflicted main Scratchpad stay intact.
Multiple results retain separate drafts, and Copy writes only after a click.
Missing or failed Notes storage keeps the result window and Copy available.

Admission is rechecked after Hub setup, during recovery-window construction and
before presentation. GUI checks use text-free generation/ticket metadata and do
not wait for the session mutex. Cancellation/new capture retires queued requests.
Closing waits for its own save; app Quit flushes all recovery windows before the
main Scratchpad, while storage/conflict errors keep the unsaved draft open.
The held-recording producer is still pending, so these windows are not yet
reachable through a functioning Command Mode shortcut.

Command results remain searchable in History but
do not count as dictated words, speaking time or dictations; Paste last transcript
continues to use a dictation row.

Thirty authored public cases cover shorter, formal, bullets and Spanish. Their
references and semantic anchors are an evaluation aid, separate from production
validation. Hand-authored references alone are not native-model acceptance.
`tools.probe_command_edit` runs every case through the pinned installed model,
retaining output, token counts, timings, source/runtime hashes and observed native
exit. The probe uses no audio, hooks, clipboard, foreground or OS text input.
It does not establish full Command Mode or owner-data acceptance.

At clean `f990074`, actual Qwen3.5 4B output passes all 30 authored checks;
the 2B comparison passes 29 and retains qualitative meaning failures despite
mechanical acceptance. Both use the same final prompt and unchanged corpus.
The earlier failures, all outputs, native exit receipts, pinned hashes and review
limits are retained in the [native edit record](../eval/commands/results/2026-11-14-native-edits/README.md).
The separate six-case untrusted-document set also passes on 4B; that narrow
measurement is not general injection-resistance acceptance. This does not change
the app's model default or make Command Mode available.
The same code source passes 3,393 tests / 12 skips, both normal cleanup gates and
the package/regression workflow. These results cover the implemented boundaries;
they do not accept the remaining full app integration.

The transport follows the pinned llama.cpp
[b12110 server contract](https://github.com/ggml-org/llama.cpp/blob/b12110/tools/server/README.md)
for `/apply-template`, `/tokenize`, schema-constrained chat output and streaming.
Native offset handling follows the Windows SDK's
[endpoint movement](https://learn.microsoft.com/en-us/windows/win32/api/uiautomationclient/nf-uiautomationclient-iuiautomationtextrange-moveendpointbyunit)
and [range endpoint](https://learn.microsoft.com/en-us/windows/win32/api/uiautomationclient/nf-uiautomationclient-iuiautomationtextrange-moveendpointbyrange)
contracts, including providers that promote unsupported text units.

```powershell
python -m pytest tests/test_command_edit.py tests/test_cleanup_preparation.py -q
python -m tools.probe_command_edit --model D:\Models\model.gguf --runtime-dir D:\Models\runtime --output D:\QA\Command-New
```

## Selected-target boundary

`ForegroundContextProvider.capture_selection()` is an explicit operation for
power-feature callers. It captures one complete selected range, bounded to 8,192
UTF-16 units, plus verified window/process/field identity. It reads neither the
surrounding document nor a larger caret prefix. The normal dictation read keeps
its original 1,024-unit bound. Empty, unsupported, overlong, malformed, unknown
password or changed fields never return partial text as a usable selection.
Unsupported selections retain verified metadata for the future copy fallback;
that fallback must still recheck sensitive state and handle clipboard races.

The existing single UIA MTA owns the cloned native range. Public snapshots carry
only immutable text, identity, ticket/generation and a tri-state read-only fact.
Before a replacement, `verify_selection()` rechecks window/process/field identity,
fresh password state, both range endpoints and exact selected text. Identical
text selected at a different position is rejected. Known read-only selections can
be read for an answer, while write verification refuses them. Unknown editability
is not a promise that paste will succeed; only the post-write confirmation can
observe success. Full hotkey and recovery UI integration remains pending.

Requests share the existing one-request owner and at-most-500-ms capture budget.
Cancellation wakes the caller and revokes late results without joining a blocked
provider or starting another owner. Scoped cleanup from an older generation
cannot cancel a newer selection. An expired published result is also revoked.
The native range/text is retired on cancellation, failure, replacement capture,
lease expiry or shutdown, on the MTA thread. If a provider is blocked, its call
must return before native references can be released; the caller still returns
within its budget. Idle expiry reads no field content. Leases are bounded to
3,660 seconds, accommodating the existing maximum recording limit.

This follows the Windows SDK's
[GetText bounds](https://learn.microsoft.com/en-us/windows/win32/api/uiautomationclient/nf-uiautomationclient-iuiautomationtextrange-gettext)
and [endpoint comparison](https://learn.microsoft.com/en-us/windows/win32/api/uiautomationclient/nf-uiautomationclient-iuiautomationtextrange-compareendpoints).
No range selection, field mutation, key input or clipboard access occurs in this
boundary. A successful verification must be used with the caller's current
cancellation/admission guard immediately before delivery; UIA is not an atomic
lock against the user or application changing a field.

## Verification scope

Synthetic policy/owner/COM tests cover exact-position changes, same-range text
changes, UTF-16 limits, no partial text, sensitive-state changes, read-only rules,
expiry, queued-result retirement, cancellation during capture/verification,
stale-generation cleanup, source-thread ownership and default-context behavior.

`tools.probe_selection` uses this process's invisible EDIT control, actual native
ranges and the real bounded owner. Direct fixture messages select and replace only known
public text. The probe substitutes its own focus identity and never reads the
active application or changes foreground focus. It checks a 1,408-unit selection,
same-text/different-position rejection, text changes, read-only behavior, password
refusal, cancellation and observed MTA/window retirement. It also confirms Unicode
and 9,000-unit replacements, refuses a deliberately truncated write, checks that
matching text elsewhere is insufficient, and refuses a newly sensitive field
before reading post-write text. The real provider-to-processor path writes History
before a bounded message to its own EDIT, confirms the result, restores a memory
clipboard and invokes recovery for an ignored fixture paste. Recognition and edit
generation are stubs in this target/delivery probe. This is not physical
focus/paste, native clipboard fallback, full Command Mode or owner-data acceptance.

The selected-target layer passes at clean `5339fa9`: 3,343 tests / 12 skips,
rules 556/556, authored adversarial 100/100 and frozen package/regression checks.
The same own-invisible-window probe passes locally and on CI. Unchanged reports,
workflow metadata, hashes and scope limits are in the
[dated record](../eval/context/results/2026-11-14-selection/README.md).

```powershell
python -m pytest tests/test_selection.py tests/test_selection_worker.py tests/test_selection_patterns.py -q
python -m tools.probe_selection --output D:\QA\OwnSelection-New
```
