# Dated website documentation qualification

P9.4 is accepted against source `5848e53e2473154813da67bac55c022864cc8323`. All specified content now uses dated
MDX: five comparisons, offline pillar, developer guide, changelog, eleven docs
including their index, Download, Privacy and Credits (22 MDX / 43 public pages).
Current source facts and model transfer sizes are documented in docs/SITE_DOCS.md.

Final local checks: 42 site cases, 234 component cases, ten Node contracts, clean
Astro diagnostics/build and Storybook build. There are no final skips, flakes or
retries. All 213 component and three Home baselines pass ordinary comparisons.
The site checks cover metadata/H1 uniqueness, HTML, complete sitemap and local
links, nested keyboard navigation, all docs without JavaScript, source-copy via
memory only, language/model tables, five original OFL notices and local-only
assets at 390/768/1440. Fifteen representative docs/resource captures are kept;
phone and desktop layouts were visually reviewed. Existing baselines stay intact.

Twenty-one Lighthouse runs across seven URLs pass unchanged budgets: minimum
performance 100, accessibility/SEO100, maximum
LCP960ms and CLS0. Actual output hashes
are retained. These simulated local results do not guarantee every device.
Real builds reject a stale nested doc and migrated Privacy resource, with exact
bytes restored. The first stale probe incorrectly expected the injected date in
the error message; the real build already refused it. Its log is preserved.
The first browser run found numeric-starting Getting started heading IDs plus
an ambiguous development-status locator and an arbitrary FAQ body-length check.
Heading labels and test targeting were corrected; full subsequent runs pass.
Original failures and final reports are retained without replacement.

A clean-source unsigned portable build qualifies the corrected bundled 4B-model
role notice. Its runtime verifies resources/native dependencies without capture,
device enumeration, clipboard, foreground or input. The source, bundle and ZIP
notice bytes match exactly; the artifact size/hash and complete bundle inventory
are retained. The app/runtime/model pins are unchanged. No installer was built:
packaging/signing/installer acceptance remains false. No ASR inference was added.

Run the standard-library verifier on this recorded source (later changes require
their own qualification):

```powershell
python eval/site/results/2026-11-15-docs/verify.py.txt --repo .
```

Add `--site-root` for actual static/Storybook outputs and `--build-root` for the
actual portable bundle/ZIP. The verifier starts no app, browser or device service.
This is a local source checkpoint: no PR, Actions dispatch, hosting deployment,
release or owner accuracy acceptance. All 60 reserved BN/TA/TE recordings remain
uninferred. The original full implementation goal and remaining P9/owner gates
stay open.
