# Offline networking

The process entrypoint installs `NetworkGuard` before starting workers. Python
socket connections, DNS lookups and UDP sends are denied outside loopback,
apart from scoped downloads and saved opt-in app update checks.
Explicit model downloads temporarily authorize only exact hosts from the bundled
model manifest, in the downloading context. Other worker threads stay offline.
Redirects must remain HTTPS on listed hosts. Files are pinned to an immutable
revision, size and SHA-256 digest and verified before the model is marked ready.
Interrupted transfers retain revision-bound `.part` files for HTTP Range resume.
Unknown or corrupt files are preserved in the model directory's `_archive`.
Only a fully verified transfer receives an atomic completion marker. Model loaders
recheck downloaded files' hashes before use.

App update checks are off by default. When explicitly enabled and saved,
startup/daily checks may read public release metadata from `api.github.com` in
their own worker context. They do not send speech or app-field data, follow
redirects, download installers or install updates. Turning them off retires
pending results. The release-page link opens only after a user action. See
[optional update checks](UPDATES.md) for the request and verification scope.

The catalog in `saydraft/models/manifest.json` includes Parakeet v3/v2 int8,
Whisper base/small/medium/turbo, Tiny Whisper language detection, Silero VAD,
the experimental Nemotron preview model, optional Qwen3.5 cleanup weights and
llama.cpp CPU/Vulkan runtimes. Catalog presence does not enable a model or qualify
an experimental feature for release. Extending it requires checking the publisher's
artifact checksums, revision, license and actual redirect hosts. Arbitrary
automatic model fetches are blocked. See [model choices](MODELS.md) and
[package installation](MODEL_PACKAGES.md).

Downloads check free disk space before requesting data, accounting for resumable
bytes and a 64 MiB reserve. If a server ignores Range, a full restart gets its own
space check before the old partial is archived. Disk-write failures preserve the
partial for another explicit resume.

Whisper inference resolves existing local files before construction and forces
local-only loading even for legacy preferences. Runtime Hugging Face download
entrypoints are restricted to existing cache entries with account-token lookup
disabled, including the tokenizer Python binding's fallback. Missing tokenizers
fail locally; explicit catalog transfers use the separate pinned-URL installer.
Setup gates Next on verified packages or a successful local-model load with
unchanged files, then checks again before Finish saves preferences. Cache load
receipts do not claim catalog SHA-256 verification. See
[setup readiness](ONBOARDING.md#readiness-and-saving).

Verify the Python boundary with:

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
python -m pytest -m offline -q
python -m saydraft.eval
```

The offline suite includes accidental HTTPS requests, direct TCP, UDP, DNS,
thread isolation, nested scopes, local connections and 50 synthetic dictations.
Logs contain destinations and timing metadata; transcript text is logged only
when debug logging is explicitly enabled.

This is an application policy for Python sockets. It does not intercept native
libraries' network stacks or sidecar subprocesses. Settings → Privacy shows this
boundary separately from an explicit, read-only Windows Firewall check. The check
counts enabled outbound block rules whose application filter matches this
process in ActiveStore. It does not establish profile/address applicability,
system-wide default-policy behavior or coverage of native helper processes.
Missing, unsupported, timed-out or denied inspection stays absent/unknown; it
never becomes a claim that the OS boundary is protected.

The inspection uses a fixed hidden PowerShell query, passes the process path as JSON
on stdin, and returns only a bounded integer count. It creates, changes and
removes no firewall rule, starts no elevation prompt, and omits provider error
details. The query follows Microsoft's [application-filter association](https://learn.microsoft.com/en-us/powershell/module/netsecurity/get-netfirewallapplicationfilter)
and [rule inspection](https://learn.microsoft.com/en-us/powershell/module/netsecurity/get-netfirewallrule)
APIs. Packaged installations also offer explicit create/remove controls for one
path-specific managed outbound block rule, with confirmation and Windows UAC.
They never block shared source Python or alter unrelated rules. Model downloads
and opt-in update checks need the rule removed. See [Verify offline](VERIFY_OFFLINE.md)
for the workflow, effective-policy limits and recovery. The disposable packaged
smoke exercises real public-audio recognition, rules, temporary History, native
WinHTTP and pinned Python downloads before, under and after the rule. Separate
helper executables, effective organizational policy and physical Windows
acceptance remain distinct from that in-process boundary.
After downloading a model, also verify real dictation with Wi-Fi disabled.

Audio remains off by default, with explicit Keep forever / Keep N days controls.
Saved time limits expire eligible app-owned recordings in the background and
preserve History text/statistics; Off/forever preserve existing files. Editing
a draft starts no cleanup. See [AUDIO_RETENTION.md](AUDIO_RETENTION.md) for cutoff,
ownership, retry leases, failure recovery and verification. The new retention and
inspection jobs report counts/status without logging text, paths or backend
exception details. Telemetry remains disabled; no opt-in analytics is added.

## First-run audio and practice

Setup's Microphone page lists available inputs after Refresh inputs. Test input
opens the selected device for a ten-second, level-only check; samples are not
retained or transcribed. Navigating setup alone does not start microphone capture.

Try it prepares an installed recognizer locally, then captures only after a
recording shortcut or Record. Its one-minute recordings, raw words and cleaned
results stay in memory. Practice uses the real recognition/cleanup path with
private History and delivery adapters, so it writes no persistent History or
audio-retention files, reads no foreground field or clipboard, and sends no paste
or Enter into another app. This remains true when daily audio retention is enabled.
Changing target, leaving the page, cancellation or shutdown stops owned work and
rejects late results. Unknown microphone/shortcut retirement blocks completion
and requests a restart. See [first-run setup](ONBOARDING.md) for the full boundary
and recovery behavior.
