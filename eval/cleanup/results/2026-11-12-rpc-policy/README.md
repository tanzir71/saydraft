# Current RPC-window policy evidence

Immutable 887e1da CPU/RTX policy runs each complete 432 exact goldens and 100
low-need adversarial skips, with zero golden/finite-preservation regressions and
all native exits observed. The index pins unmodified reports and retained local
case-journal digests. Runs are sequential, offline and isolated from other benchmarks.

CPU four-thread decoder samples are 24.06/23.42/23.44 tok/s, median 23.44. It
accepts zero model replies: all results use rules, bypass or budget/need skips.
This is valid fallback-policy evidence and cannot establish hybrid model quality
or the plan's 25 tok/s Standard threshold. RTX samples are 137.21/143.90/147.74;
it accepts 213 exact replies. All 100 adversarial inputs per backend skip for low
need, providing zero new generation credit. Forced-model proof remains separate.

Explicit one-case thread diagnostics retain three exact 60-token samples each:
two threads 13.75/14.74/15.05 tok/s; six threads 12.43/16.63/12.06. All diagnostic
native exits are observed. These smaller runs cannot establish full quality or
tier acceptance and do not change app thread settings. Four threads remain the
best measured configuration in this comparison, below Standard's threshold.

Preparation is excluded from per-case timing, no audio or OS delivery is used,
and no latency/default acceptance is performed. Earlier faster-instance evidence
and the whole-clip/background release replays remain unchanged beside this directory.
