# Clipboard selection transaction, 14 November 2026

Clean application source **`48e6dc5`** passes [Windows CI](https://github.com/tanzir71/saydraft/actions/runs/43548756248):
**3,610 tests / 12 skips**, 459.92 seconds, rules **556/556**, normal cleanup
adversarial checks **100/100**, and the separate firewall/update jobs. The
[unsigned package workflow](https://github.com/tanzir71/saydraft/actions/runs/43548756197)
passes build/resource/notice audits, disposable install/uninstall and existing
frozen regressions. The retained [frozen analysis](package-analysis.toc)
includes `saydraft.insert.selection_copy`; [bundle audit](package-bundle.json)
retains the package inspection payload.

The raw analysis now retains its native `.toc` extension and unchanged SHA-256.
Its initial `.toc.txt` filename caused the runtime-source legacy-engine guard to
scan the report's deliberately excluded-engine list in the documentation-only
`6bb2849` CI run. The filename correction changes neither application sources
nor the runtime guard; the retained report bytes remain identical.

**This is a transaction component.** It is not connected to held Command Mode,
does not add app clipboard access and does not qualify physical Ctrl+C, original
unsupported-field leases, end-to-end fallback or full frozen Command acceptance.
P7.1 remains unchecked. [Integration limits](../../../../docs/COMMAND_CLIPBOARD.md)
describe modifier release, sensitive-field checks, Copy-only fallback and target
clipboard-history/sync policy.

## Native result

The unchanged [CI report](ci-native.json) names the clean source and completes
three authored selections through actual native clipboard handling:

| Selection | UTF-16 units | Complete text | All original formats restored |
|---|---:|---|---|
| Plain text | 20 | Exact | All 11, exact |
| Bengali / Arabic / emoji | 16 | Exact | All 11, exact |
| Maximum accepted selection | 8,192 | Exact | All 11, exact |

The original public fixture includes RTF, a DIB image, Unicode text, all three
privacy flags and Windows synthesized formats. The probe compares each format's
fingerprint and order after each transaction. It also verifies a pre-input
refusal, no pending recovery, owned EDIT retirement, private desktop/station
closure and return to the original surface.

An invisible **owned EDIT** receives **WM_COPY** on a newly created private
window station/desktop. Native GetClipboardOwner/PID and sequence checks, text
capture, duplication/restoration and resource retirement are real. The admission
guard is a controlled fixture. There is no foreground read, UIA/worker/model
integration, microphone, owner clipboard access or injected keyboard input.
WM_COPY is not physical Ctrl+C. No local native clipboard run was performed.

The CI ZIP has numeric/current report aliases with identical bytes: **one native
measurement**. Both aliases and the archive hash are retained in the [index](index.json).
The 12 explicit suite skips concern existing external model fixtures; this
native private-surface probe ran and passed.

```powershell
python -m tools.probe_selection_copy --output D:\QA\New-Private-Copy-Probe
```

The tool has no owner-clipboard mode. Its pytest wrapper runs on disposable
Windows CI only. Private-surface creation refusal is an explicit skip before
clipboard access; subsequent failures fail the check.

## Memory-only checks and provenance

The focused clipboard/handles/inserter/input/reentry set passes **165 tests**.
It covers complete bounded Unicode, all-format restoration, refusal before copy,
unchanged/stale data, owner/sequence races, delayed rendering, cancellation,
partial input, busy reading and pending recovery. A failed delayed read after a
sequence change and a target keeping the clipboard busy both retain restoration
ownership. The running app's normal paste route is unchanged.

The [index](index.json) pins all five raw payloads, the native archive, private
full logs and package receipt archive. [CI metadata](ci-run.json) and
[package metadata](package-run.json) name the exact accepted application source.
No test or packaging completion is credited as full Command Mode acceptance.
