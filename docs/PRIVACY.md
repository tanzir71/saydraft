# Offline networking

The process entrypoint installs `NetworkGuard` before starting workers. Python
socket connections, DNS lookups and UDP sends are denied outside loopback.
Explicit model downloads temporarily authorize only exact hosts from the bundled
model manifest, in the downloading context. Other worker threads stay offline.
Redirects must remain HTTPS on listed hosts. Files are pinned to an immutable
revision, size and SHA-256 digest and verified before the model is marked ready.
Interrupted transfers retain revision-bound `.part` files for HTTP Range resume.
Unknown or corrupt files are preserved in the model directory's `_archive`.
Only a fully verified transfer receives an atomic completion marker. Model loaders
recheck downloaded files' hashes before use.

The catalog covers Parakeet v3/v2 int8, Whisper base/small/medium/turbo and Silero VAD.
It is in `saydraft/models/manifest.json`. Extending the
catalog requires checking the publisher's artifact checksums, revision, license
and actual redirect hosts. Arbitrary automatic model fetches are blocked.

Downloads check free disk space before requesting data, accounting for resumable
bytes and a 64 MiB reserve. If a server ignores Range, a full restart gets its own
space check before the old partial is archived. Disk-write failures preserve the
partial for another explicit resume.

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

The helper uses a fixed hidden PowerShell query, passes the process path as JSON
on stdin, and returns only a bounded integer count. It creates, changes and
removes no firewall rule, starts no elevation prompt, and omits provider error
details. The query follows Microsoft's [application-filter association](https://learn.microsoft.com/en-us/powershell/module/netsecurity/get-netfirewallapplicationfilter)
and [rule inspection](https://learn.microsoft.com/en-us/powershell/module/netsecurity/get-netfirewallrule)
APIs. Packaged rule installation plus complete native/sidecar boundary testing
remain P8.6.
After downloading a model, also verify real dictation with Wi-Fi disabled.

Audio remains off by default, with explicit Keep forever / Keep N days controls.
Saved time limits expire eligible app-owned recordings in the background and
preserve History text/statistics; Off/forever preserve existing files. Editing
a draft starts no cleanup. See [AUDIO_RETENTION.md](AUDIO_RETENTION.md) for cutoff,
ownership, retry leases, failure recovery and verification. The new retention and
inspection jobs report counts/status without logging text, paths or backend
exception details. Telemetry remains disabled; no opt-in analytics is added.
