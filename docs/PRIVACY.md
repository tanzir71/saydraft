# Offline networking

The process entrypoint installs `NetworkGuard` before starting workers. Python
socket connections, DNS lookups and UDP sends are denied outside loopback.
Explicit model downloads temporarily authorize only exact hosts from the bundled
model manifest, in the downloading context. Other worker threads stay offline.
Redirects must remain HTTPS on listed hosts. Files are pinned to an immutable
revision, size and SHA-256 digest and verified before the model is marked ready.
Corrupt and interrupted files are preserved in the model directory's `_archive`.

The current catalog covers Whisper base, small and medium. It is in
`saydraft/models/manifest.json` until the approved package rename. Extending the
catalog requires checking the publisher's artifact checksums, revision, license
and actual redirect hosts. Arbitrary automatic model fetches are blocked.

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
libraries' network stacks or sidecar subprocesses. The planned Windows Firewall
control provides that OS boundary; it is not implemented by this milestone.
After downloading a model, also verify real dictation with Wi-Fi disabled.
