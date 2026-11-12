# Production cleanup policy measurements

Unmodified source-d0845b4 reports retain both complete RTX and partial CPU
measurements. The index pins report bytes and the retained local journal digests.
Runs are sequential with no transfers or competing benchmarks; networking is
blocked and independent handles observe all native exits. Delivery is simulated.

RTX 2B completes 432 golden cases exactly, with 213 accepted replies, 92 low-need
skips, 118 bypasses and nine other fallbacks/skips. All 100 adversarial inputs are
low-need skips: zero new generated adversarial replies. No finite preservation
failures or golden regressions occur. Full policy completion is true; forced
model measurement remains false.

CPU 0.8B completes only 63 golden cases: ten accepted replies, one timeout with
rules fallback, and all 63 exact. Its three live rates are 27.81/29.20/28.98 tok/s.
The timeout closes the owned server and the runner refuses to count subsequent
unprepared cases. Policy completion is false; this is retained failure evidence,
not full quality or Standard acceptance. Completed replies expose up to 1.60x
underprediction, motivating a more conservative predictor before another run.

The app cap remains 800 ms with a 50 ms reserve. Static preparation is explicitly
awaited outside per-case timing, with per-case calibration/setup metadata. No ASR,
key release or real insertion is measured. These reports cannot establish the
end-to-end latency target or select a default.
