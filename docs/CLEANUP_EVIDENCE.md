# Retained native cleanup evidence

The offline evidence checker compares complete CPU 0.8B and Vulkan 2B policy
measurements with separately forced native model measurements. It performs no
downloads or inference. Policy completion cannot substitute for actual accepted
replies, and 100 low-need adversarial skips cannot substitute for forced generation.

Checks cover immutable report digests, source commits, pinned candidate identity,
clean/isolated full corpora, observed native exits, unchanged corpus/prompt hashes,
at least 92% strict hybrid exact output, zero golden/must-keep regressions, positive
accepted reply/token evidence, and three finite exact 60-token decoder samples.
The report separately compares the three-sample median with the 25/40 tok/s tier
thresholds; interactive prediction continues to use the minimum. Below-threshold
speed does not turn a quality pass into tier acceptance. Sparse CPU model use
remains explicit, and tier/performance acceptance stays pending when its target is missed.

Policy reports must match current cleanup/dictation/processor source fingerprints.
Forced adversarial reports must match the current preservation guards and prompt
contract. Source text permits only LF/CRLF variants across checkouts; raw native
report bytes remain strictly pinned. Source or corpus changes require fresh
measurements for the affected evidence. No latency or default-model acceptance
is inferred from a successful quality check.

Run `python -m tools.check_cleanup_evidence` to assess the retained current
RPC-window policy reports against the independent forced-model reports. Custom
indexes can be selected explicitly with `--policy-index` / `--forced-index`.
The current CPU policy report is correctly refused: it contains zero accepted
model replies at a 23.44 tok/s median. It proves safe rules fallback and cannot
complete a hybrid model-quality measurement. The current RTX report contains
213 accepted replies, but both target recipes are required for a full check.

Mandatory CI wiring remains pending a current CPU hybrid measurement with real
accepted replies. Existing rules/adversarial thresholds remain enforced in CI.
No below-tier or zero-call result is promoted to make this evidence check pass.

Validation: 1418 tests pass with four optional native skips; rules 432/432,
authored adversarial checks 100/100, and Ruff/diff checks pass. Fifteen synthetic
report tests cover positive model evidence, stale source, exact thresholds,
regressions, incomplete runs, generation credit, immutable bytes, unsafe paths,
portable line endings and separate rate-target reporting. These fixtures are
test data, not new native measurements. Running the checker on current retained
reports at `c240d92` returned the expected refusal: `Rules fallback cannot earn
accepted model credit`. Subsequent native-startup changes also invalidate those
older source fingerprints until new measurements are collected.
