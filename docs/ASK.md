# Ask about selected text

Status, 14 November 2026: Ask is connected from the default-off Pro/Labs opt-in
through selection review, local generation, History and an independent answer
Scratchpad. P7.3 remains open pending actual-model and native read-only browser
acceptance. The owner desktop test remains stopped.

## Using Ask from source

1. Choose Pro in Models, then review the editing model's size and licenses in
   Settings → Labs. Use Download / Resume if it is not installed already.
2. Enable **Ask about selected text** and save Settings. This opt-in is separate
   from Command, Translate and dictation cleanup; it never starts a download.
3. Select a readable passage and release **Ctrl+Win+A**. The shortcut can be
   changed or disabled in Settings → Shortcuts.
4. Review the frozen selection, then type a question or choose Summarize, Explain
   or Rewrite. Normal dictation can fill an already open question field.
5. Read the answer in its separate Scratchpad, edit it if needed, and use Copy
   when ready. The current note stays active; the original document is not edited.

Read-only selections are eligible. Ask uses UI Automation and does not use
Command's optional clipboard-copy fallback. Unsupported, changed, sensitive or
oversized selections are refused. Model answers require review and can be wrong.

## Implemented boundaries

`cleanup/llm/ask.py` sends the complete selected text and question as escaped JSON
data through the existing authenticated local model transport. It counts the
rendered chat before generation, reserves the output budget, and refuses an
oversized context rather than truncating the selection. Only a complete stream
with an exact answer object is accepted. Partial, cancelled, malformed, tool,
added-control and newly invented URL output is refused. These checks constrain
transport and presentation; they do not prove that every model answer is factual.

`CommandModelSession.ask_about` uses the existing revocable editing-model slot.
It works independently of dictation cleanup, observes cancellation and shutdown,
and releases its own manager without closing a successor. Its independent
default-off Labs opt-in requires Pro and rechecks admission before generation.
The existing explicitly installed shared 4B editing model and processor are
verified on the worker thread; a missing model leaves the question available.

`core.ask.capture_ask_source` explicitly disables clipboard fallback, verifies
readable UIA selections (including read-only text), and revokes the original
lease before returning plain source values. It refuses changed, sensitive,
unsupported, copied or retired selections. `core/ask_controller.py` reserves this
capture on the native action thread before any question window can take focus.

`core/ask.py` then consumes an immutable, reviewed source snapshot. It has no source
document, insertion, recording or clipboard port. The controller fences
operations and queued UI callbacks independently from the dictation session, so
voicing a question does not revoke the reviewed source. Complete answers are saved before
presentation. Failed generation leaves the question available for retry; a
History failure preserves the complete answer for independent recovery.

Cancel and Settings changes revoke metadata before model retirement, without
waiting for native shutdown or an admitted History write on the GUI thread.
Already committed answers remain in History, while retired popups are suppressed.
A new capture or navigation invalidates delayed review/answer presentation;
an existing hands-free recording cannot be claimed by the Ask chord. Only the
exact cancelled push-to-talk prefix may finish retiring ahead of a new review.

History stores the question and answer with task `ask`, action, model, timing and
source hash/length provenance. It does not separately store the reviewed excerpt;
an answer can still quote the excerpt when requested. Ask rows are excluded from
dictation totals, audio-duration completeness and Paste Last. History labels
question/answer copies and Markdown export accurately, and blocks ordinary audio
retry, automatic reinsert and transcript diff for these rows.

`ui/ask_window.py` reviews plain read-only source text and accepts a typed question
or Summarize, Explain and Rewrite actions. It prevents duplicate requests,
preserves questions on failure, cancels on close and rejects retired updates.
The review area scrolls at small sizes while feedback and Cancel/Close remain
visible. A second presentation gate prevents a delayed window from activating
after another capture starts. `ui/ask_answer.py` uses independent revision-aware
Notes drafts, preserves Copy when storage fails, and participates in shutdown
flushing without replacing or activating the current note. Opening an answer
does not construct Hub/Settings or discover microphone devices.

## Verification and remaining work

The earlier component commit `8ec5670` passes full Windows CI: 4,081 tests with
12 explicit skips, rules 556/556, adversarial 100/100 and the package workflow.
These results do not qualify the subsequent integration.

The connected implementation passes 384 broadly focused worker, shortcut,
config, persistence and Qt tests. After visual review, 38 lifecycle/window/flow
checks also pass with the final scrolling and late-presentation guards. Forty
owned offscreen renders cover both themes at 1x/2x, including Labs opt-ins and
downgrade states, complete/recoverable answers and small-window feedback. Rules
556/556 and adversarial 100/100 pass. These use authored text, fake model/clipboard
ports and owned SQLite, without owner microphone, foreground reads or OS input.
Fresh full CI/package verification of this integration follows.

The first clean native run at `891bc7c` completes all nine cases with unchanged
source/pins and both native exits observed, but passes only **8/9** meaning
anchors. Its Bengali answer changes Saturday to Friday. This is a genuine
factual error that structural validation accepts, retained in the
[native diagnostic](../eval/ask/results/2026-11-14-selection/README.md). The prompt
now explicitly asks direct factual answers to copy names, dates, numbers and
short answer phrases from the source; a separately frozen follow-up set and
unchanged original cases still need inference. No accuracy improvement is
claimed yet. The answer window explicitly asks users to review generated text.

Still required:

- Run `python -m tools.probe_ask --models-dir <explicit-installed-cache>
  --device Vulkan1 --output <new-evidence-directory>` against the pinned model.
  Nine authored cases cover the three actions, questions, missing source facts,
  source-instruction refusal and English/Spanish/Arabic/Bengali smoke answers.
  Anchors are smoke checks, not exhaustive semantic or multilingual quality.
- Verify native read-only browser article selection on a disposable remote
  desktop, with no writes to the source and with queued cancellation guards.
- Complete physical/packaged workflow acceptance when separately permitted.

The source-only availability and deferred owner desktop acceptance remain as
documented in the [parity plan](../WISPR_OFFLINE_PARITY_PLAN.md).
