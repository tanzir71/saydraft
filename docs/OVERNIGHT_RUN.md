# Overnight follow-up · requested 15 November 2026

The owner explicitly requested an overnight run from the remaining work. The
recording failure reported during preparation was fixed first; the run now pins
clean `44ed9c458a78e84e55751b827ed71b96114632ae`, matching the replacement unsigned
portable. This resumes the selected evidence work without reopening all parity
requirements or changing the unsigned-distribution decision.

## Selected serial batch

1. Full Pro release-latency matrix: 160 cold/warm public-audio cases, with real
   ASR/cleanup/History and memory capture/input ports. This fills the missing
   full measurement after the delivery-target patch.
2. CPU Qwen3.5 0.8B forced cleanup: all 556 goldens and 100 adversarial cases.
3. GPU Qwen3.5 2B forced cleanup: the same complete corpora.
4. CPU 0.8B production-policy replay: the same complete corpora and real budget gate.
5. GPU 2B production-policy replay: the same complete corpora and real budget gate.

Each cleanup stage also records three 60-token decoder samples. Forced and
policy generation stay distinct; rules fallback earns no model-generation credit.
These are measurements, not automatic model/default promotions. Original
thresholds, corpus contents, decoder settings and interactive time limits stay
unchanged. Only repository-authored text and the bundled public WAV are used.

Expected duration is approximately 3–6 hours, bounded at **eight hours total**.
The controller owns each stage's whole process tree, waits for its exit before
the next stage, records actual exit codes and retains failed/partial results.
There are no automatic retries. A timeout terminates only the owned stage tree;
it does not create a qualified report. A process-scoped keep-awake request is
released on exit; Windows power settings and the display are not changed.

## Safety and scope

No microphone, clipboard, foreground window, host keyboard/mouse injection,
owner dictation or profile lookup is part of the overnight batch. Refusing ports
install before app imports. Pro uses the previously approved GPU metadata and
the existing explicit Vulkan adapter. Models/runtime are verified existing
files; the queue downloads nothing. CPU/RAM metadata are limited to capability
fields needed by the benchmark; no audio-device discovery occurs.

The separate host input-list/level-only diagnostic was explicitly approved for
the microphone bug. It saved/transcribed no audio and is not expanded into an
overnight recording authorization. Native Windows acceptance still needs the
approved disposable guest. Signing, public release, external workflows,
deployment and model promotion are not part of this run.

## Execution and evidence

QA root: `D:/Saydraft-Codex-QA-20261112-01a1cbc7`.
Planned queue directory: `overnight-44ed9c4-20261115-r1`.
Its `status.json` records the actual controller PID, active owned stage PID,
heartbeat, command/source hashes, completed outcomes and final status. Each
stage has a separate sibling output directory, guard records, raw report and
exit receipt. Cleanup journals may retain only the authored test text/outputs
for independent scoring and diagnosis; no owner speech is present.

The controller's real exit-zero, exit-seven and forced-timeout process-tree
probes pass at `overnight-queue-probe-44ed9c4-20261115-r1`. These stdlib probes
validate supervision only, not model quality or latency. The source scripts
are retained under `docs/launch/overnight/` as non-executable references.

To stop after the current stage, create `STOP_AFTER_CURRENT` inside the queue
directory. `STOP_NOW` requests termination of the current owned tree. Neither
is a pass or an instruction to restart the stage. Keep performance stages free
of competing local builds/transfers/model jobs. After terminal exit, independently
verify the original journals/source/model bindings and summarize every failed
gate before updating the handover. Starting the queue alone is not completion.
