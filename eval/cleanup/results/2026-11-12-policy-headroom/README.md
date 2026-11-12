# Cleanup policy with prediction headroom

Unmodified immutable-source ec64d01 reports retain sequential CPU/RTX runs with
networking blocked and no transfers or competing benchmarks. The index pins the
report bytes and retained local case-journal digests. Both native exits are observed.

Both backends complete all 432 goldens exactly, with zero golden regressions and
zero finite preservation failures. CPU 0.8B accepts two exact replies (0.47/0.43 s),
skips 220 on budget and 92 on need, and bypasses 118 Raw/Code cases. Its live
decoder samples are 30.17/30.00/29.52 tok/s. RTX 2B accepts 213 exact replies, with
92 low-need skips, 118 bypasses and nine guarded fallbacks/skips. All 100 runtime
adversarial inputs per backend skip for low need and provide zero generation credit.

Policy completion is true for both. Forced model measurement remains false; the
earlier separately measured forced-adversarial reports retain their own meaning.
The CPU result demonstrates conservative rules fallback with very sparse model
use; its 100% hybrid exact score is not a 100% standalone model score.

The unchanged app cap is 800 ms with a 50 ms reserve and uniform 2x prediction
headroom. Static preparation is awaited outside per-case timing. No audio, release
event or actual OS insertion is measured. End-to-end tier acceptance, CI evidence
threshold integration and default selection remain pending. The original partial
CPU timeout is preserved in the adjacent 2026-11-12-policy directory.
