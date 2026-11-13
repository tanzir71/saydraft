# Optional app update checks

App update checks are **off by default**, including profiles created before
this setting existed. Dictation and cleanup work without enabling them.

Open **Settings → Privacy → App updates**, select **Check for app updates** and
save preferences. Saydraft checks at startup, when the setting is first enabled,
and once every 24 hours while running. **Check now** requests another check.
Repeatedly saving the same setting does not repeat the startup request.

A newer stable version shows a notice. **View release** opens that version's
GitHub release page in your browser. Download and install an update yourself;
Saydraft does not download installers, run them, or replace its own files.
Model setup and model downloads remain separate.

Clear the checkbox and save to stop future checks. An in-flight metadata request
may finish, but its result is retired and cannot restore an update notice or
release button. Closing the app cancels queued work without waiting for a
request. Network errors leave dictation available and show a retry message in
Settings. A repository with no published stable release shows that status.

## Network and validation

The only request is an unauthenticated HTTPS GET to
`https://api.github.com/repos/tanzir71/saydraft/releases/latest`. It sends a
Saydraft version user agent, without transcript, field, clipboard, history or
device data. The client does not read GitHub credentials or ambient proxy
settings. Redirects are rejected. Responses are limited to 256 KiB with a
five-second socket timeout.

The Python NetworkGuard grants `api.github.com` only in the check's own worker
context and retires that permission afterward. It does not give the dictation
worker a general internet exception. The default-off path does not construct a
transport, resolve DNS or open a socket. This is a Python policy check; the
separate native/firewall boundary still needs its own acceptance.

Only a published, non-draft, non-prerelease, three-part version newer than the
installed version can be offered. The release page must match this repository
and its version tag. The client ignores release-body markup and asset URLs;
the opened page URL is constructed from the validated version.

The endpoint and public-release behavior follow
[GitHub's latest-release API](https://docs.github.com/en/rest/releases/releases#get-the-latest-release).
Drafts and prereleases are not update candidates. The unsigned draft used for
release-automation verification is therefore not offered by this check.

## Developer verification

`tests/test_updates.py` covers the saved opt-in, scoped networking, response
limits, malformed metadata, redirects, version ordering, cancellation and
retired generations. `tests/test_updates_ui.py` uses owned Qt fixtures and fake
transports/openers to check responsiveness, notices, saved settings and release
actions without opening a browser.

The separate CI metadata-smoke job invokes the production client with its
default off, then explicitly with `--enabled`. The latter makes a real public
metadata request and proves that the API exception is retired afterward. It
downloads no binaries and starts no desktop app. The job can be rerun without
repeating the full offline unit suite if GitHub is temporarily unavailable.

```powershell
python -m tools.probe_updates
python -m tools.probe_updates --enabled
```
