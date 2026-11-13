# Combined native soak — 2026-11-14

The clean, isolated source `2d96f62ff86284455bd399f5350a2fc960f1b821`
completed 200 consecutive cycles in one process and private History profile.
The real SessionWorker, processor and Inserter used synthetic capture/ASR/focus
and in-memory keyboard/clipboard. Native cleanup used the verified CPU b12110
runtime and the pinned developer-only 15M GGUF fixture, with its explicit context
override. This is lifecycle/regression evidence, not cleanup quality or ASR/tier
acceptance.

| Check | Result |
|---|---:|
| Requested / completed cycles | 200 / 200 |
| Failures / slow worker cycles | 0 / 0 |
| Saved History rows / checked paste events | 200 / 200 |
| Simulated clipboard restoration failures | 0 |
| Genuine complete one-token native streams | 100 |
| Requested / observed terminations after tokenization | 100 / 100 |
| Owned native processes / observed exits after shutdown | 100 / 100 |
| Current-process RSS before / after cycles | 46,391,296 / 48,013,312 bytes |
| RSS growth | 3.50% |
| Slowest worker cycle | 1.137 s |

The RSS baseline followed initial service/model readiness and History schema
preparation; the end reading preceded shutdown. Preparation between cycles is
recorded separately, not counted as a GUI freeze. Native processes were closed
and independently observed before success was reported. The normal stream and
injected-fault requirements both passed; rules output alone earned no generation
credit.

`native-200.json` retains the original report bytes. `index.json` pins its SHA-256
and the private metadata journal hash. Every journal row matches the corresponding
report cycle; all 199 recorded source fingerprints match the implementation,
allowing only checkout LF/CRLF differences. The private SQLite database and
journal remain in the QA store. No model weights are published.

The memory clipboard exercises actual Inserter ordering and restoration logic;
the owner's Windows clipboard, microphone, foreground and physical input were
not used. This result establishes the scoped native regression gate. Physical
Windows insertion/clipboard acceptance, CPU hybrid credit and cold/warm
release-to-text qualification remain separate work. Earlier failed diagnostic
attempts remain in the [deadline evidence](../../../cleanup/results/2026-11-13-deadline-policy/README.md).
