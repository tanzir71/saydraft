# Website component library qualification

P9.2 is accepted at source `da4b480719786e476a7b96235a15cc2bd5ded1f2`: all 23 specified components, including the
three documentation parts, have 71 built Storybook states. All 213 committed
component PNGs cover 390/768/1440 widths. Three separate Home baselines are also
committed in site/tests. The final ordinary component run passes 234 checks;
the final site run passes 30, including static/no-JavaScript behavior at each
actual project viewport. There are no skips, retries or flaky results.

The library checks compare every snapshot, refuse page overflow and external
requests, check flat-surface text contrast, and exercise keyboard tone switching,
independent groups, memory-only copy success/denial, checksum disclosure,
keyboard table scrolling, and full/reduced SVG motion. Representative component
states and all three Home layouts were visually inspected. New Home tone
controls, shared Footer/credits/keycaps, Download copy/development state and MDX
contents navigation are connected to actual static pages. Future release and
package-manager fixtures remain visibly labelled in Storybook and absent from
the public Download page. No real clipboard API is exercised by these checks.

Astro builds 33 pages with zero errors/warnings/hints; Storybook builds all
states. Seven Node contracts pass, including negative HTML structure/ARIA/ID
checks and the existing date/release behavior. Fifteen mobile-simulation
Lighthouse runs across five pages pass every original budget: minimum
performance99, accessibility100, SEO100, maximum LCP960ms and zero CLS.
The final rebuilt site's 57 output files match the Lighthouse-tested bytes
exactly. Local results do not guarantee every device or connection.

Original failures remain unchanged. Initial browser runs encountered unrelated
projects on ports4173/6006; those processes were preserved and these checks use
42731/42732/42733. The first Astro integration passed an Astro JSX object as a
React visual prop; a named slot corrects that boundary. Early HTML validation
found the now-fixed KeyCaps ARIA naming plus valid React boolean/void formatting
that differed from Astro. Two formatting-only rules allow both HTML5 forms;
negative structure/ARIA/duplicate-ID checks remain enforced. The first new HTML
fixture used a lowercase doctype; its fixture was corrected. Storybook copy
tests initially also matched its hidden diagnostic code; scoped locators retain
the full actual copy/denial assertions. No-JavaScript text helpers omit noscript;
the final test reads its DOM textContent and independently requires visibility.
This changed the test locator, not the rendered hint. Initial/new-state snapshot
captures precede final ordinary comparisons. A final root-directory npm build
invocation failed before building; the retained site-directory follow-up passes.

The first LHCI run ended at Chrome's error document before a page measurement.
The explicit server and equivalent owned headless Chrome navigation return200;
direct Lighthouse scores100/100/100, LCP960ms, CLS0. The readiness pattern now
matches Astro's actual ready message instead of the hostname echoed by npm.
The following full15-run LHCI run passes; the earlier failure and diagnostic
records remain. This evidence does not establish the transient error's cause
beyond the observed startup/navigation boundary.

Verify source, report, snapshot and metric evidence with the standard library:

```powershell
python eval/site/results/2026-11-15-components/verify.py.txt --repo .
```

Add `--site-root` with the explicit D: worktree/site folder to check every actual
static site and Storybook output file. The verifier does not start a browser,
server, application or clipboard service. App runtime/package bytes are unchanged
from the preceding qualified Whisper-mode checkpoint. Owner accuracy and the
60 reserved BN/TA/TE recordings remain untouched. P9.1/P9.3–P9.7 and the full
original implementation goal remain open. All workflows remain manual-only;
this checkpoint creates no PR, Actions run or hosting deployment.
