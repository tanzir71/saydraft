# Tag-to-draft release verification

Tag [`v0.1.0-dry-run.20261114`](https://github.com/tanzir71/saydraft/tree/v0.1.0-dry-run.20261114)
points to `7a9486a2cf106e87386585eaf5dd7438e6048245`.
The [Draft release workflow](https://github.com/tanzir71/saydraft/actions/runs/43510576550)
completed successfully and created draft release **444758925**. Exact-source
[main CI](https://github.com/tanzir71/saydraft/actions/runs/43509272069) passed
**3,195 tests / 12 skips**, rules **556/556**, authored validator **100/100**.

The workflow verified a fresh unsigned build, frozen resources and notices,
the disposable installer lifecycle, source/tag/version matching and artifact
hashes. It uploaded four assets:

| Asset | Bytes | SHA-256 |
|---|---:|---|
| `Saydraft-0.1.0-Setup.exe` | 103,976,636 | `6c1f95ed4f956d9d8cd43819999cce196fc62d78a55eb47aa8f5fd470452b8ad` |
| `Saydraft-0.1.0-win-x64.zip` | 160,033,099 | `b22d604da4fd6b91041ceb0d2cdf58ec1434d4e4de4033bb7c2b2f568516f914` |
| `SHA256SUMS` | 186 | `7af066873eee9eff9e5d775c064b4f8f303d0481c96482ed3a16ea6afe9bfcaa` |
| `release-manifest.json` | 673 | `5e55bd0868563cfc112eb034e6356c6f3d46cd15a0ab61fcd98aaddb93765cd2` |

GitHub's computed binary-asset digests match the release manifest. The two small
manifest/checksum assets were downloaded and hashed; their checksum entries
match both binaries. All assets are in the `uploaded` state. Binary assets were
not downloaded during the separate isolated native latency run. The earlier
[P8.1 evidence](../2026-11-14-notices/README.md) independently checks downloaded
binaries from its own producer; do not substitute those older hashes here.

The raw release manifest and checksum bytes are retained unchanged. The latter
is named `SHA256SUMS.txt` locally to preserve its original CRLF bytes through
Git attributes. `workflow.json` is the successful workflow snapshot;
`verified-release.json` records draft status, source tag, asset digests and
hashes of the private original API responses. `index.json` hashes four retained
files. The notice inventory remains 38 components / 506 files with index hash
`7f33cd43bd47dcc5f94439d5fdd048ab94be58e4d56ac144b52d6cb882a39964`.

This completes P8.2's real dry-run acceptance. The release is **draft** and
**unsigned**, with no publication timestamp. Signing/G5, corresponding-source
delivery for publication, owner accuracy and physical Windows acceptance remain
separate. Draft visibility requires repository access.
