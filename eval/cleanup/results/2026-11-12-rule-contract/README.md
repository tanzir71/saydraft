# Rules-cleaned contract reevaluation

Unmodified reports use immutable source `b32a03e`, pinned Qwen/Gemma artifacts
and the unchanged 432 golden/100 adversarial inputs as the original baseline.
`index.json` records report and retained local journal digests. Git preserves JSON
bytes across platforms.

Full RTX/Vulkan runs completed all inputs and three exact 60-token samples, with
native exits observed. CPU debug runs contain only two golden/two adversarial
cases plus three 60-token samples. Earlier runs overlapped transfers and some driver caches were primed;
these are not isolated tier or release-to-text measurements. Quality reports
separate accepted output, rules fallback and Raw/Code bypass. Residual punctuation,
casing and phrasing mismatches remain. All five candidates have full quality
measurements; isolated latency and selection remain pending. No model is selected.
See [the results table](../../../../docs/MODELS.md#rules-cleaned-contract-reevaluation).
