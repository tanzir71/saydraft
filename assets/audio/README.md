# Performance fixture

`benchmark.wav` repeats the existing `tests/fixtures/hello.wav` three times and
retains the first eight seconds. Mono 16 kHz PCM16 samples are retained exactly.
The asset is bundled through the existing `assets/` packaging rule.

- Source SHA-256: `5c080d296295bd085baa14f604e66e908e825d84f96581aea4b4902a46a29cd0`
- Benchmark SHA-256: `cc6d363cc90b6c99427041ba6366e334131b05101a142761ae84b2a8b5e2c5ab`

This is a small throughput fixture. It provides no independent recognition
reference and is not an accuracy corpus. Its transcript is never inserted or
saved to dictation history by the performance check.
