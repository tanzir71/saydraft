# Isolated cleanup component measurements

Unmodified reports use source `b32a03e` after all transfers and other local
benchmarks finished. `index.json` pins report and retained local journal digests.
Both runs complete 432 golden/100 adversarial inputs, three exact 60-token samples
and observed native exits.

These direct quality runs use a 120 s deadline and predate interactive prefix
preparation. They expose cold/prefix/long-input costs; they do not enforce the
production need-score/budget gate or measure ASR/native insertion. Driver caches
are primed. Residual exact regressions remain and no model is selected.
See [the table and limits](../../../../docs/MODELS.md#isolated-component-latency).
