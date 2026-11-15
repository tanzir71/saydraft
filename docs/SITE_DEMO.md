# Prepared-example demo

`site/src/pages/demo.astro` ports the original four-example simulation to
`/saydraft/demo/`. `site/src/data/demo.json` preserves every original raw and clean
sentence. “Meeting notes” is labelled “List notes” to distinguish the prepared
bullet-list example from the app's experimental meeting-recording feature.
The page uses the shared tokens, BarDemo, keyboard caps, navigation and footer.
The footer links to it as Interactive demo.

The page identifies every result as prepared text. It never uses the microphone,
speech recognition, cleanup inference, downloads, clipboard or text insertion.
It makes no accuracy, latency or live-transcription claim. The displayed app
shortcut is the current Ctrl+Win; the old F9 and “Inserted locally” labels are
replaced by an explicit simulation and “Draft ready”. P10.2's optional live
WebGPU/microphone demo is a different, still-open task.

Native radio controls select examples with mouse or keyboard, and details/summary
opens or closes raw words. All four prepared outputs remain readable with
JavaScript disabled. JavaScript enhances only playback and reset. Motion progresses
through listening/cleaning/ready; reduced motion finishes directly. Reset, a new
example, a changed motion preference and leaving the page cancel pending timers.
Late callbacks cannot replace a newly selected example. Status announcements are
polite, and controls keep an explicit keyboard focus ring.

The route has its own canonical and social preview with `noindex,follow`.
It is excluded from both sitemaps, readable exports and the unsubmitted IndexNow
payload. Public indexable routes remain 44; the static build now contains 46 HTML
pages including the demo and 404. FAQ schema verification considers only marked
FAQ components, not raw-text or checksum disclosures; it still requires exact
visible question/answer agreement.

Browser checks exercise all four pairs, denied device/clipboard/script-network
APIs, zero third-party requests, real keyboard navigation, cancellation with a
controlled browser clock, full/reduced motion, no-JavaScript reading, contrast,
overflow and noindex/export behavior at 390/768/1440. Node verification compares
the four pairs with the original legacy HTML without executing its script.

## Legacy transition

The separate [G9 candidate](launch/legacy-site/README.md) contains a minimal
rename banner and a checked `git mv` script. An isolated Git fixture proves both
old HTML files retain their bytes and are detected as 100% renames, while Vercel
configuration stays identical. Its banner has inspected phone/desktop captures
and passes the same HTML validator. This does not replace the old website's
source or prove the hosted old URL changed.

P9.1 remains unchecked until its required archival transition and branch-workflow
preview are satisfied. The owner currently requires local validation and direct
main pushes, with all five workflows manual-only and no Actions dispatch. G9
requires the reserved owner decision before the old site's source is replaced.
No Vercel project deletion is part of this work.

An unauthenticated public request to `https://voicetray-offline.vercel.app/`
on 15 November returned HTTP 402. Its page body and banner were not verified.
The prepared source and isolated fixture do not establish P9.7 live acceptance;
that requires a later successful hosted-page check. No hosting setting changed.

## Local qualification

The 15 November checkpoint passes 75 site, 240 component and 19 Node checks
without skips, flakes or retries; 99-file type diagnostics have no errors,
warnings or hints. All 219 component, three Home and three Demo baselines pass
ordinary comparisons. Twenty-one Lighthouse runs on the existing seven public
pages score 100/100/100. Three added demo runs score 100 performance/accessibility;
their SEO score of 63 has only the expected noindex/is-crawlable failure. Across
all 24 runs, maximum LCP is 960 ms and CLS is zero. Three fresh Home runs qualify the corrected responsive image. The other 21
reports are retained only after checking all 189 loaded local-file references
against the old and corrected manifests. Only Home HTML and three new image
files differ; those other routes use identical files. The 206 production files
stay byte-identical through the fresh Home performance checks. See the frozen
[demo qualification](../eval/site/results/2026-11-15-demo/) for raw reports,
original failures, the mismatch build, source witnesses and verifier.

A follow-up image check reproduced a 1080-pixel Hub asset displayed at 1160
pixels on desktop. ProductShot now uses lazy-image `sizes="auto"` with a
viewport fallback and a 1160-pixel variant; an explicit original aspect ratio
keeps layout stable across rounded image variants. The regression check reads
the actual selected image and verifies its pixel width covers its displayed
width at each tested viewport. Source PNGs and their native provenance remain
unchanged. This follows the [HTML sizes standard](https://html.spec.whatwg.org/multipage/images.html#sizes-attributes).
