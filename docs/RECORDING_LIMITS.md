# Recording duration

New profiles default to a 20-minute recording cap (`recording.max_seconds=1200`)
with a warning at 19 minutes (`recording.warning_seconds=1140`). The recorder's
default bounded audio buffer also covers 20 minutes. Timers start when the
microphone is armed, after model preparation and context capture.

The warning says “Recording will stop at 20:00. Finish up soon.” The cap follows
the normal stop/ASR/cleanup/History/delivery path and reports that recording
stopped at the configured limit. Repeated or stale timer callbacks cannot stop
another session or persist/deliver the same recording twice. Cancel/release
retires scheduled timers; generation checks also reject callbacks already in
flight.

Saved explicit limits remain unchanged, including the former 600/540-second
defaults. Missing limits and migrated legacy text settings use the new defaults.
Change them through Settings → Cleanup → Recording cap / Warning time; a warning
of zero disables it. Existing custom values continue to determine both recorder
capacity and worker scheduling.

Session tests use a controlled clock and scheduler to exercise 19:00/20:00,
one-stop persistence/delivery, custom caps, a disabled warning and callbacks from
a cancelled earlier recording. They open no microphone and make no 20-minute
ASR or latency claim. Hands-free gestures, paste-last and P5.5 manual acceptance
remain separate work. Desktop interaction remains stopped at the owner's request.

Validation: ordinary full suite 1864 pass, five explicit native/model skips;
golden 472/472; adversarial 100/100; Ruff/diff pass. The local full-run log is
`build/qa/recording-limit-full.stdout.log`.
