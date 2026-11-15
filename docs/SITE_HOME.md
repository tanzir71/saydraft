# Home page

The owner-supplied landing v2 design supersedes the composition described below.
See [Landing v2](SITE_LANDING_V2.md) for the current homepage. The previous
native product images and their provenance remain available for the demo and
reference library; v2 uses explicitly illustrative, semantic HTML examples.

## Previous home implementation

Home implements the thirteen-part §9.6 composition using the approved §9 tokens:
development announcement, navigation, hero, open-model credits, qualitative
speed section, three cleanup examples, six feature rows, shortcuts, privacy,
dated comparison, ten FAQs, final CTA and expanded footer. The language section
also retains all nineteen approved language guides in alphabetical order.
The footer keeps the owner's portfolio and support credit, adds Dictation and
Notes tiles and groups links into Product, Compare, Docs and Project columns.
Notes links to a dated Scratchpad/experimental-meeting guide.

The source status is explicit. No 1.0 announcement, current-source installer,
accuracy guarantee, fabricated word count, review or speed benchmark is implied.
Command Mode and English live preview disclose their experimental setup. Meeting
notes disclose their remaining native, duration and quality acceptance. Model
setup still requires the user to review and start the download; selecting a
language starts no transfer.

## Images and motion

The Hub and Bar images are renders of actual Qt classes with public sample text,
not reconstructed UI. `site/tools/render_product.py` runs at 2× scale using the
offscreen Qt platform, isolated profile directories, memory ports and a Python
network guard. Imports of audio SDKs, hooks and native clipboard modules are
barred. Native Windows loading, clipboard access, URL opening, device enumeration
and recording callbacks are barred. No owner's desktop, microphone, audio device,
clipboard, application, input hook or personal profile is used.

Run the producer from the repository root, with a fresh output path outside the
checkout, when desktop app controls change:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
python site/tools/render_product.py --output D:/Saydraft-QA/product-2x
```

The producer records its source, hash, access flags and eighteen captures. Five
selected PNGs and their hashes are tracked in `site/src/assets/product/source.json`.
The app source at capture is `99b65c529fa162ab2433b7e87442f64a7856f10f`.
Astro Picture generates local responsive AVIF/WebP with PNG fallbacks, explicit
dimensions and lazy loading. Captions identify public samples. The full-size Hub
link preserves the original 2× screenshot.

G10 photos remain an owner decision. The speed and final sections use the plan's
approved token duotone fallback. The hero retains the illustrative Ribbon/BarDemo
simulation, with an explicit no-microphone label. Reduced motion skips the
animation and exposes its completed result; native navigation, tones and FAQs
also work without JavaScript. All React components are rendered statically.

## Facts and verification

`site/src/data/home-comparison.json` holds twelve source-linked cells for four
products. The build refuses a comparison date older than 120 UTC days or in the
future. Standard online Win+H is distinguished from on-device Fluid enhancements
and the separate offline Voice Access feature. Pricing is described without
hardcoded quotas or a superiority claim. All five detailed comparison guides are
linked beside the table, whose own scroll region supports keyboard access.

The public repository star count is verified during each build, dated visibly
and included in the static HTML. Zero is valid. An unavailable or invalid response
fails the build instead of publishing an invented count. Browser readers make no
GitHub request, and stars are not supplied as application review ratings.

Local checks cover phone/tablet/desktop layout, outer and inner sheet gutters,
CTA/text contrast, native keyboard navigation, image decoding, no third-party
page requests, JavaScript-disabled content, all page metadata/links and matching
FAQ schema. Separate component baselines cover the changed navigation/footer and
real/zero star states. Lighthouse keeps the original performance, accessibility,
SEO, LCP and CLS budgets. These checks do not establish owner audio accuracy,
full desktop acceptance or an external search-engine validation result.

Local qualification on 15 November: 63 site, 240 component and 17 Node checks
pass without skips, retries or flakes. Type diagnostics cover 95 files with no
errors, warnings or hints. All 219 component and three Home snapshots pass. All
21 Lighthouse runs score 100/100/100, maximum LCP 960 ms and zero CLS. The 201
built output files are unchanged through performance testing. The frozen
[Home qualification](../eval/site/results/2026-11-15-home/) includes the original
failures, restored stale-date build, native captures and source/output verifier.
