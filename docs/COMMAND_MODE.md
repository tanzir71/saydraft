# Command Mode implementation

P7.1 remains in progress. The experimental held-recording route now connects
Labs/Pro/model admission, instruction ASR, selected-text generation, History,
guarded paste/confirmation and independent Copy recovery. It currently requires
a safely readable selection. The Ctrl+C capture fallback and full
physical/frozen Command acceptance remain open; the checkbox stays off by default.

The [clipboard transaction foundation](COMMAND_CLIPBOARD.md) now provides an
explicit guarded one-copy/snapshot/restore boundary with shared recovery. It is
not wired into this experimental route yet; unsupported UIA fields still refuse
before Command audio. No new clipboard capture occurs in the running app.

## Using the experimental selection path

1. Use the Pro tier, selected in Models or supported by the saved performance check.
2. In Settings → Labs, review Command's model/runtime sizes, licenses and credits.
   Choose Download / Resume, then enable experimental Command Mode and Save.
   Downloading does not enable it or change ordinary cleanup/speech settings.
3. Select text, hold **Ctrl+Win+Alt**, and wait for the Command label before
   speaking a short editing instruction. The distinct tick plays when sounds are
   enabled. Release to edit. Esc cancels.

Standard shows **Needs Pro tier** before Command target/model/microphone work.
Password/changed or unreadable selections refuse before Command audio. Known
read-only selections can produce a validated edit for Copy without input.
An earlier legitimate Ctrl+Win dictation prefix can already have started normal
capture. The Command route cancels/discards that prefix and waits for its serial
arm/finalizer to finish before a new instruction capture. It does not relabel the
prefix as Command. A pre-existing hands-free session is preserved.

The original selection is captured before deferred start, then verified again
after model preparation. A pending start has an explicit generation acknowledgement:
release before acknowledgement invalidates that request and never calls
`stop(None)` on another recording. Release during model/speech preparation cannot
open a late microphone. New starts, Settings, storage work and other capture tools
respect the reservation; Settings can finish after an already listening Command.

Instructions bypass ordinary dictation cleanup, snippets, live-preview selection,
correction learning and voice Enter. Recognized instructions that fail generation
or validation remain in History, without newly reading/storing document text.
If History fails, an explicitly labelled **Command instruction** recovery window
keeps the heard words. Valid generated edits retain instruction provenance in
History's result details and Markdown/CSV exports. Command audio retention follows
the saved preference, but its audio cannot be retried through the dictation route.
History offers Copy for Command entries, without a quick paste that bypasses the
original selection guard. Paste last transcript and dictation statistics remain
limited to dictation rows.

## Command model ownership

The app catalog now pins the measured **Qwen3.5 4B Q4_K_M** weights, card and
Apache-2.0 notice for the experimental Command task. It is excluded from the
cleanup picker; ordinary 0.8B/2B defaults remain unchanged. The choice follows
the narrow 30-case native comparison below, rather than treating 2B's mechanical
acceptance as proof that it preserves meaning.

`command_choice()` requires the default-off `labs.command_mode` opt-in and Pro
tier. Other tiers receive `needs_pro` before any installed-file or device access.
The backend uses an explicit Command preference or the saved hardware report.
`installed_command_config()` runs on a worker and fully verifies the command
weights/card/license and runtime cache. Missing files return no configuration;
only the separate explicit setup function downloads the displayed licensed
package, with the existing pause/resume, staging and disk checks. There is no
automatic download on opt-in, capture, language selection or inference.
The Labs setup group provides explicit download/pause/resume controls and an
independent processor preference. Its license links follow the active foreground
palette in both themes. Saving preview controls preserves the Command preference.

`LocalLLMCleaner.command_session()` reserves one revocable editor independently
of the ordinary cleanup enable setting. It closes/detaches the old preparation
and manager before Command starts. Normal cleanup/warm/review calls are refused
during that reservation; a late old cleanup reply is discarded even if the
Command session has already ended. Real managers share the existing process
slot, so a replacement cannot launch until the prior process's exit is observed.
Cancellation, startup failure and timeout close the temporary owner. No GUI
thread joins a starter. Closing restores lazy ordinary cleanup; its next request
constructs a fresh manager and prepares a fresh prefix. Repeated old-session
closure cannot retire a successor. Synthetic tests cover both switch directions,
pending process exit, concurrent closure and cancelled/late results.

The clean native owner-switch probe at `6099772` completes original cleanup
preparation, Command 4B editing and fresh cleanup preparation, with all six owned
native process exits observed and four authored edit examples passing. It waits
for owned Command exit before the final prefix check; ordinary app cleanup can
use rules during asynchronous retirement/warmup. This proves neither product
latency nor the held recording flow. Unchanged reports and both earlier failed
diagnostics are in the [ownership record](../eval/commands/results/2026-11-14-model-ownership/README.md).

The native owner-switch probe uses an explicit private cache and authored text:

```powershell
python -m tools.probe_command_session --models-dir D:\QA\VerifiedAppCache --output D:\QA\CommandOwner-New
```

It checks cleanup preparation, exclusive 4B editing and fresh cleanup preparation
without speech, foreground, clipboard, hooks or OS text input. This is component
verification, not full Command Mode acceptance.

## Local edit and delivery boundaries

The lower `LocalLLMCleaner.edit_selection()` compatibility method reuses the
ordinary installed, serial sidecar; the Command session exposes the same editor
contract on its separately admitted model. Editing has
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
The held-recording producer queues these recovery requests after a failed or
unconfirmed delivery. Model/target/microphone work and clipboard/UIA calls never
hold the worker mutex across GUI/native message handling. History admission uses
a separate short serialized write boundary; cancellation before that admission
drops work, and a row already committed is preserved.

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
observe success. Clipboard capture and physical input acceptance remain open.

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

The combined confirmation/recovery code at clean `5d5bbf2` passes 3,438 tests /
12 skips, both normal cleanup gates and the package workflow. The expanded native
probe passes all 13 cases locally and on CI; eight clean offscreen recovery
renders cover both themes at 1x/2x. Reports, images, the earlier fixture/inventory
failures and exact scope limits are in the
[confirmation/recovery record](../eval/context/results/2026-11-14-confirmation-recovery/README.md).

The model ownership and Settings integration at `ea2d25b` pass 3,487 tests /
12 skips, rules 556/556, normal cleanup adversarial checks 100/100 and package
verification. Native ownership source `6099772` completes both model switches,
six observed owned exits and four authored edit examples. Its model/session
scope is unchanged by the later Labs-save correction. The
[ownership record](../eval/commands/results/2026-11-14-model-ownership/README.md)
retains that proof, both native diagnostics and the initial four-failure CI.
That checkpoint did not cover held recording. The current route is described
above; clipboard capture and full packaged Command acceptance remain open.

The connected held-recording and Labs setup at clean `c9380ae` pass **3,538 tests /
12 skips**, rules 556/556, normal cleanup adversarial checks 100/100, both auxiliary
CI jobs and the unsigned package workflow. Local and CI owned-window probes each
complete 18 cases, including five actual worker scenarios with scripted audio and
models. Twelve clean offscreen renders cover setup/gating/instruction recovery in
both themes at 1x/2x. Raw reports, images, exact scope and the earlier dirty
diagnostic are in the [held-recording record](../eval/commands/results/2026-11-14-held-recording/README.md).
This proves the connected readable-UIA flow under controlled ports, without
physical microphone/hooks/clipboard/paste or full frozen Command acceptance.

```powershell
python -m pytest tests/test_selection.py tests/test_selection_worker.py tests/test_selection_patterns.py -q
python -m tools.probe_selection --output D:\QA\OwnSelection-New
```
