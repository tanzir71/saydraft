# Declining exhausted RPC windows

The retained whole-clip CPU replay includes one tokenizer timeout after ASR had
nearly exhausted the two-second release budget. No model generation occurred,
and rules reached History/delivery, but the expired transport closed its owned
server and initiated recovery. Its report remains unchanged in
`eval/cleanup/results/2026-11-12-release-replay/`.

Interactive policy now declines a request with 50 ms or less available for RPC
work, after the separate 50 ms fallback/delivery reserve. It checks before model
construction, after prompt assembly and after each tokenization stage. If the
first tokenization consumes that window, the second RPC and generation do not
start. The actual request deadline and configured cap remain binding.

This conservative minimum is an internal admission rule, not a new timeout or a
promise that all RPCs complete within 50 ms. The scientific forced-quality path
and background preparation keep their independent explicit budgets. Skips log
metadata/reasons and receive no complete model-response token credit. They still
save rules before normal delivery.

The full policy runner also retains final live decoder calibration in the top-level
report, before closing the server. This makes the three exact 60-token rates
available to an offline evidence checker alongside the per-case local journal.
Fresh native corpus measurements remain necessary before acceptance.
