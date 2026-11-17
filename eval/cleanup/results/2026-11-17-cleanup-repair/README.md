# Comma repair and bounded CPU cleanup qualification

All four complete native stages pass the unchanged offline checker: evidence
validity, exact output and decoder speed. Each stage covers **556 golden + 100
adversarial cases**, with zero golden regressions or recorded finite-preservation
failures. These are developer fixtures, not owner speech accuracy acceptance.

| Stage | Source | Exact goldens | Accepted golden model replies | Median decode |
|---|---|---:|---:|---:|
| CPU forced | `7e09bae` | 556/556 | 384 | 25.12 tok/s |
| Pro Vulkan forced | `7e09bae` | 556/556 | 390 | 148.03 tok/s |
| CPU production policy | `aa30ea1` | 556/556 | 1 | 27.50 tok/s |
| Pro Vulkan production policy | `aa30ea1` | 556/556 | 269 | 150.16 tok/s |

CPU uses pinned Qwen3.5 0.8B Q4_K_M; Pro uses pinned Qwen3.5 2B Q4_K_M on the
existing Vulkan adapter. Both retain four threads and llama.cpp b12110. Model,
runtime, prompts, corpus and raw report fingerprints are retained in the indexes.
Every owned native child exit was observed. There are no model weights here.

The structure guard rejects model-added comma punctuation adjacent to the literal
word “comma,” including the three prior regressions. It preserves the rules
result rather than silently editing a bad reply. The CPU startup path now loads
speech before optional cleanup calibration/warmup, so Saydraft's own ASR loading
does not compete with that calibration. This does not establish faster kernels
or qualify co-loaded interactive latency.

The first full policy attempt at `7e09bae` stopped after 216 cases: an admitted
request predicted 733.8 ms against 746.5 ms remaining, then timed out after
757.0 ms. That partial run is retained and earns no completion credit. `aa30ea1`
adds 50 ms of RPC/scheduling allowance to admission while keeping the 800 ms cap
and existing prediction headroom. Both corrected full policy runs have zero
timeouts. Forced runs do not use admission, so their earlier source remains
explicit and is not relabeled.

CPU thread, scheduling, placement and passive-wait diagnostics showed variable
host conditions and no reliable improvement over the existing four-thread
default. No tuning setting was adopted. **CPU policy accepted only one golden
model reply**; most text still used fast deterministic rules. The scoped checker
pass is not broad semantic/hybrid acceptance, a hardware-tier promotion, owner or
multilingual accuracy, or full release-to-insertion latency acceptance. Policy
adversarial cases skip for low need; the separate forced stages provide 100
token-counted adversarial generations each.

`raw-evidence.tar.gz` contains 59 immutable original reports, journals, logs,
guards, diagnostic producers, partial failures and independent verification.
`manifest.json` pins every member and the archive hash. `verify_matrix.py` inside
the archive independently checks case identity, exact text/Enter flags, UTF-8
hashes, counts, token credit, refusing-owner flags and native exits. Before/after
proof replays the original comma failures and startup ordering with fake ports.
The supplemental qualification receipt is byte-pinned separately in the manifest.

Run `python -m tools.check_cleanup_evidence` to verify the retained reports without
inference, extraction, downloads or host input/audio/clipboard access. Guarded
native runs use only public files, their own sidecars and approved GPU metadata.
No VM work or owner desktop/audio access was performed. Later app/UI changes do
not relabel these immutable cleanup source commits.
