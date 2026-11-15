# Labs license-link contrast — controlled verification

Clean `1cd39e36595c4fbcca1afdf25ad3ee052e7ff919` passes six focused checks without
skips in 6.10 seconds. The English-preview license and model-credit links now
follow their label's text palette on live palette/style changes. URLs, visible
legal details, keyboard focus, accessible name and explicit-only download behavior
are preserved. No model, language, inference or default changes.

Two tests traverse light → dark → simulated high contrast → light → dark at
actual 16px and 32px font sizes. They check both real rich-text anchors against
the rendered page background at ≥4.5:1 contrast, keep both exact URLs, and require
no implicit download. Ten native owned-widget PNGs are retained. Four existing
Labs/download checks also pass, using fake transfers and report providers.

`confirmed-before` uses the exact old `a58b7b4` Labs source with the corrected,
bundled-font test fixture: both font sizes fail dark-theme contrast (blue
`#0000ff` on `#111111`). Its four PNGs and failure logs remain unchanged.
`initial-unregistered-fonts` and `font-fixture-failure` retain the first diagnostics:
the isolated renderer omitted font registration, producing missing glyphs and
unresolved font metrics. Those captures are not product qualification. The app
already registers its bundled fonts; the fixture now does too. `corrected-working`
retains the passing pre-commit checks, separately from the final clean run.

The manifest binds 58 raw logs/XML/guard records, captures, source witnesses,
runner and summary files. No owner device, audio, input, foreground, clipboard,
profile, database or model binary is involved. The small offscreen checks overlap
the separate frozen accuracy-only comparison; its timings remain diagnostic.
Physical display scaling, native high contrast, Narrator and the rest of P6.7
remain unqualified. Other help/model links are outside this focused check.

The existing unsigned `625c987` portable predates this fix. A fresh portable is
queued after the active ASR job ends; this source result does not claim the old
ZIP contains the changed module. No release, PR, Actions dispatch or deployment.

Offline verification, with Git history and no app imports:

```powershell
python eval/ui/results/2026-11-15-labs-license/verify.py.txt --repo .
```
