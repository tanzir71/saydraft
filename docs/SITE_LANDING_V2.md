# Landing v2 implementation

The 16 November publication links the confirmed working unsigned Windows preview
from the announcement, navigation, hero and final CTA. The download page includes
the real ZIP, SHA-256, exact size, release notes and portable setup; the changelog
uses published GitHub releases. [Local build and Pages publication](SITE_PUBLICATION.md).

The owner's `design/landing-v2/` exports and `LANDING_V2_HANDOVER.md` define this
redesign. Home is implemented in `site/src/pages/index.astro`, using the existing
Astro/React stack and reusable components. It uses real HTML, CSS and local fonts;
the supplied screenshots are references, not page backgrounds.

The page includes the announcement and pill navigation, struck-filler hero and
instrument panel, facts/open-models sheet, three-step workflow, five accessible
cleanup tabs, feature bento and shortcuts, privacy signal path, sourced comparison,
alphabetic language wall, ten native FAQs, final CTA and creator-credit footer.
Examples are explicitly illustrative and never request a microphone. The hero
replays listening, tidying and delivery; reduced motion shows the end state.

All nineteen approved languages retain their guide links. Native names carry
language and direction attributes, including Arabic, Persian and Urdu. Short
display names are data fields rather than separate language definitions. Model
downloads remain explicit reviewed setup actions. No language packs, installer,
performance score or accuracy guarantee is invented by the redesign.

## Shared appearance and scope

`design/tokens.json` contains the website v2 palette and typography. The desktop's
unchanged palette is retained in `design/app-tokens.json`. The existing generator
reads both files and still checks all twelve outputs. The unsigned microphone
build and its app appearance are preserved.

Familjen Grotesk 500/600, Martian Mono 400 and Doto 700 are self-hosted from exact
Fontsource 5.3.0 packages. Instrument Serif and Geist Mono are removed from website
dependencies and requests. Complete original licenses remain in `site/public/licenses/`.
Existing Bengali/Arabic fallbacks are bundled; other scripts use system fallbacks
to avoid full CJK and Indic font transfers. Fontsource's [Familjen documentation](https://fontsource.org/fonts/familjen-grotesk/install)
and package metadata establish the font family and licensing source.

The library now has 26 component groups and 94 Storybook states. No React hydration
runtime is needed for the landing page. Cleanup tabs use keyboard arrows/Home/End;
tone previews use native radio controls; FAQs and mobile navigation use native
details/summary. Focus, reduced-motion and forced-color rules remain available.

The desktop content column is 1120px with 160px margins at 1440px. Dark sheets
retain outer gutters and inner padding. On mobile, the language wall keeps all
nineteen entries, the comparison scrolls inside its own region, and all ten FAQs
remain present. This makes the mobile page longer than the abbreviated reference.
Sources/dates remain visible in each comparison cell. Small deleted text uses an
orange strike with readable muted lettering; the decorative orange headline period
has an equivalent screen-reader period. Guide buttons keep their colors inside
prose containers.

The hero filler fades to 50% rather than the reference's 24%. At the supplied
paper/ink colors, 24% produces only 1.69:1 contrast. The implemented 50% yields
about 3.42:1, meeting large-text AA while retaining the strike and faded treatment.
The rendered-opacity browser check and Lighthouse both enforce this constraint.
Inactive tone labels use ink on the sunk surface to keep small text above 4.5:1.

## Local verification

Validation records and desktop/mobile captures are retained at
`D:/Saydraft-Codex-QA-20261112-01a1cbc7/landing-v2-20261115-r1`.
The [committed verification record](../eval/site/results/2026-11-15-landing-v2/)
contains logs, source/output hashes, complete compressed Lighthouse reports and
the final full desktop/mobile captures.

- Clean npm 11.19.1 installation, build and Storybook complete successfully.
  Astro reports zero errors, warnings or hints and builds 46 static pages,
  including 44 indexable URLs. All twelve generated token outputs agree.
- All 19 content contracts and 81 ordinary site cases pass. The component run
  passes 294 cases; nine FeatureRow baselines still contained the old lighter
  tone labels. After inspecting and deliberately updating only those labels,
  all nine pass ordinary comparisons on the same source, covering all 303 cases.
  The later hero-only opacity adjustment affects no component story.
- All 21 Lighthouse reports across seven URLs score 100 for performance,
  accessibility and SEO. Maximum LCP is 960ms; maximum CLS is 0.02064, below
  the unchanged 0.05 limit. Earlier contrast failures and attempts are retained.
- Final captures return HTTP 200 with no external requests or browser errors.
  Root overflow checks cover 320–1920px, and the desktop column measures
  1120px at x=160. The served homepage matches the built file byte for byte.
- External fonts total 208,936 bytes versus the prior 132,988 bytes, plus
  3,928 bytes of inline Doto font data. The approximately 80KB increase stays
  within the handover's approximately 120KB budget. Instrument Serif is absent.

Run from `site/`:

```powershell
npm ci
npm run build
npm run content:test
npm test
npm run storybook:build
npm run test:components
npm run lighthouse
```

The lockfile preserves the original transitive pins; the font change was checked
with a clean npm 11.19.1 installation. When reusing an already running local
preview, set `SAYDRAFT_TEST_PORT` and `SAYDRAFT_TEST_REUSE_SERVER=1`. The normal
test command starts its own fresh server by default. Browser captures use the
explicit local `tools/qa-landing-v2.mjs` script with an unused output directory.

No Actions dispatch, PR, release, indexing submission or hosting deployment is
part of this local implementation. Publishing follows the owner's separate
GitHub Pages workflow.

## Publication receipt — 15 November 2026

Landing v2 is live at [the public website](https://tanzir71.github.io/saydraft/).
Pages run [43743639329](https://github.com/tanzir71/saydraft/actions/runs/43743639329)
succeeded for source `8452a45dc7db797edc887213dfeb0b89e782fbd7`. Direct HTTP and
served CSS checks confirm the v2 hero, Familjen typography, nineteen language
guides and Tanzir credit. The earlier publication-pending statements above are
historical checkpoints. Routine desktop delivery does not dispatch workflows.
