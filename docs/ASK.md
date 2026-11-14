# Ask about selected text

Status, 14 November 2026: local answer, persistence and review-window components
are implemented. Ask is not exposed in the app yet. P7.3 remains open until the
selection controller, Labs/Pro admission, shortcut, answer Scratchpad and native
read-only browser workflow are connected and verified.

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
and releases its own manager without closing a successor. The connected feature
will require its own default-off Labs opt-in and Pro admission, using the existing
explicitly installed shared 4B editing model and processor.

`core.ask.capture_ask_source` explicitly disables clipboard fallback, verifies
readable UIA selections (including read-only text), and revokes the original
lease before returning plain source values. It refuses changed, sensitive,
unsupported, copied or retired selections. The caller must reserve capture and
fence the subsequent UI request.

`core/ask.py` then consumes an immutable, reviewed source snapshot. It has no source
document, insertion, recording or clipboard port. The caller must verify the
selection, retire its UIA lease before opening the question window, and fence
each operation and queued UI callback. Complete answers are saved before
presentation. Failed generation leaves the question available for retry; a
History failure preserves the complete answer for independent recovery.

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
visible. It uses injected callbacks and is not registered with the app shell yet.

## Verification and remaining work

The 205 focused local History/client/session/review checks pass, as does a
separate 43-case capture/processor/window follow-up. The review widget also passes its nine controlled tests, including
long Unicode questions and small-window reachability. Sixteen owned offscreen
renders cover review, busy, failure and ready states in light/dark at 1x/2x.
These use authored text and fake callbacks, without microphone, owner clipboard,
foreground reads or OS input. Fresh clean CI for these components follows.

Still required:

- Connect the verified capture helper to the reserved native action thread
  before any question window takes focus.
- Connect the revocable worker/controller, independent Labs/Pro gate, shared
  explicit model setup and shortcut with recording-prefix and hands-free guards.
- Present answers in independent Scratchpads whose Notes writes do not activate
  or replace the current note; preserve storage/Copy recovery and shutdown fences.
- Verify the full source-to-model-to-History-to-Scratchpad path, native read-only
  browser selection, cancellation/settings races and actual local model behavior.

The source-only availability and deferred owner desktop acceptance remain as
documented in the [parity plan](../WISPR_OFFLINE_PARITY_PLAN.md).
