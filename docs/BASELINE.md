# Dictation baseline

Measured: 2026-11-11T18:11:15.874567+00:00

- platform: Windows-11-10.0.26200-SP0
- python: 3.13.17
- processor: AMD64 Family 25 Model 80 Stepping 0, AuthenticAMD
- logical_cpus: 12
- mode: cached ASR + rules
- model: base
- audio_file: hello.wav
- audio_seconds: 3.0
- iterations: 20
- idle_rss_bytes: 37580800
- warm_rss_bytes: 706494464
- insertion: memory clipboard/keyboard with real restore delays; no foreground paste

| Phase | Stage | Samples | p50 (ms) | p95 (ms) |
|---|---|---:|---:|---:|
| cold | vad | 1 | 50.474 | 50.474 |
| cold | stt | 1 | 24304.035 | 24304.035 |
| cold | rules | 1 | 1.949 | 1.949 |
| cold | llm | 0 | not measured | not measured |
| cold | cleanup | 1 | 2.017 | 2.017 |
| cold | history | 1 | 5.716 | 5.716 |
| cold | insert | 1 | 301.799 | 301.799 |
| cold | total | 1 | 24664.111 | 24664.111 |
| warm | vad | 19 | 2.323 | 6.273 |
| warm | stt | 19 | 1549.957 | 2134.611 |
| warm | rules | 19 | 0.17 | 0.312 |
| warm | llm | 0 | not measured | not measured |
| warm | cleanup | 19 | 0.218 | 0.404 |
| warm | history | 19 | 11.259 | 25.962 |
| warm | insert | 19 | 300.744 | 302.021 |
| warm | total | 19 | 1864.813 | 2447.097 |

Cold means first transcription in this process; disk caches may already be warm.
The first ASR sample includes model load. Warm samples reuse the same engine.
Total is release-to-simulated-insertion, including history and restore delays.
RAM is this benchmark process, excluding the Qt shell and any sidecars.
This fixture is a smoke measurement, not an owner-clip accuracy or hardware-tier result.
No models are downloaded, no foreground windows or user history are modified,
and reports contain no transcript text.

Reproduce: `python -m tools.bench --audio tests/fixtures/hello.wav --iterations 20`.
Run separate processes with 3/10/30/90-second owner fixtures for full latency evidence.
