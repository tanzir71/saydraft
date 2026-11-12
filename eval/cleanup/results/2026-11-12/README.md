# Partial native cleanup baseline

These unmodified generated reports use source `536a5cb` and the pinned candidate
catalog. `index.json` records report and retained local journal SHA-256 digests.
Git preserves JSON bytes across platforms so those digests remain reproducible.

`*-vulkan1.json` completed 432 golden and 100 runtime adversarial cases on the
RTX 3060. `*-cpu-debug.json` covers only two cases from each suite and three
60-token samples. Transfers were concurrent; no run declares isolation. Native
child exit was observed in all four runs.

Measurement completion means the requested run finished. It does not mean quality,
latency or tier acceptance. Both full runs fail the strict golden quality gate;
fallback passes and bypasses are reported separately from accepted model passes.
No model is selected. Other candidates, isolated measurements and prompt/format
contract resolution remain pending. See [the results table](../../../../docs/MODELS.md#cleanup-baseline-measurements-2026-11-12-incomplete-matrix).
