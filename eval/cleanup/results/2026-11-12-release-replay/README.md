# Native release replay baseline

Unmodified ec3a680 reports retain three sequential runs, twenty samples each at
3/8/20 seconds. The index pins report bytes and retained local journal digests.
Networking is blocked; all insertion stubs verify SQLite persistence first. No
microphone, hooks or OS keys are used. Every owned native exit is observed.

These baseline runs use instantaneous capture and whole-clip recognition after
release, with background ASR disabled. The normal minimum-recording guard is
disabled only in the injected replay session. Warm model/prefix preparation is
excluded before release. Fixture History databases remain in the local directories.

| Mode | 3 s audio p50/p95 | 8 s audio p50/p95 | 20 s audio p50/p95 | Accepted replies |
| --- | --- | --- | --- | ---: |
| Rules | 0.479 / 0.547 s | 0.950 / 1.071 s | 2.001 / 2.817 s | 0 |
| CPU 0.8B policy | 0.671 / 0.863 s | 1.104 / 1.203 s | 2.969 / 3.725 s | 0 |
| RTX 2B policy | 0.822 / 1.304 s | 1.473 / 1.970 s | 2.455 / 2.734 s | 40 |

All three measurements complete, but none meets every latency target. The CPU
uses rules throughout: 59 budget skips and one tokenizer timeout near an exhausted
release deadline, before generation. Its restarted server also exits cleanly.
RTX accepts all short/medium cases and skips every 20-second case on budget.
Whole-clip ASR dominates long-case latency. Completion is not target acceptance.

Compare the production background-ASR path with real-time replay before claiming
end-to-end parity. Repeated public audio does not establish owner accuracy,
live-device/real-application behavior, broad tier acceptance or default selection.
