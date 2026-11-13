# Opt-in app update acceptance

Producer: [`222913d`](https://github.com/tanzir71/saydraft/commit/222913dc92d0db58a569d84689ce84a158281982).
[CI](https://github.com/tanzir71/saydraft/actions/runs/43516930104) and the
[frozen package/lifecycle build](https://github.com/tanzir71/saydraft/actions/runs/43516930111)
passed. This completes P8.5's update-check acceptance.

- Windows regression suite: **3,237 passed / 12 skipped**, 409.38 seconds.
- Rules: **556/556**. Authored adversarial validator: **100/100**.
- Real default-off probe: disabled; no transport or outbound request.
- Real opt-in probe: **HTTP 404 / no published stable release**. The API scope
  was retired afterward. No installer download, browser or desktop app launch.
- Owned Qt tests cover saved preferences, responsive background checks,
  startup/daily scheduling, notices, explicit canonical release-page opening,
  opt-out/close/destruction and stale callbacks. Published-release behavior uses
  controlled valid metadata and a fake browser opener, without owner input.

`ci-run.json` and `package-run.json` retain the successful source-matched workflow
snapshots unchanged. `probe-results.json` contains the two timestamped live probe
results decoded from the original CI log. `index.json` hashes those three files
and records the original private CI/package-log hashes.

The earlier verification failures remain recorded in the index:

- `821e8c0`, CI 43514844329: **3,232 passed / 12 skipped / 1 failed / 2 errors**.
  A large parameter value expanded into an overlong Windows pytest environment
  variable during setup/teardown, and the checklist lacked the new CI commands.
  The same payload test now uses a short explicit ID, and the checklist includes
  both commands. No validation case was removed or relaxed.
- `85bd34d`, live job 132198646464: the client returned unavailable with its API
  exception retired. That version did not record a diagnostic cause; it remains
  undiagnosed. The newer client records only safe HTTP/category metadata. The
  subsequent live check passed without weakening the check's success criteria.

This record covers application update metadata and owned UI behavior. It does
not establish signing, native firewall coverage, owner ASR accuracy, physical
Windows input or automatic installer updates. Installation remains manual.
The separate isolated Lite latency baseline continued during remote verification;
no local tests, builds, native jobs or model transfers competed with it.
