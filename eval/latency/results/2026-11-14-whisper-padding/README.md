# Whisper padding diagnostic

Source `0bbc3e159147eff16e85852a8e7735d4eb12e3ba`, 72 completed warm decoder-only
cases with three repeats. All baseline output identities are stable. All encoder
calls complete, all features are retained and the temporary Python hooks restore.
The owned process exits zero; installed source files and the probe hash match.

Shorter padding improves the shortest English timing but changes the repeated
English, Bengali, Arabic and direct-silence outputs. Production padding remains
unchanged. Exact baseline equality is not accuracy acceptance; no new WER,
release-latency, timestamp, physical-input or owner-accuracy claim follows.

`report.json`, `cases.jsonl` and `process.json` are unchanged originals, hashed by
`index.json`. No transcript text or audio is published in these records. Method,
fixture attribution, limits and results: [padding spike](../../../../docs/spikes/whisper-padding.md).
