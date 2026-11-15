# Landing v2 local verification

This checkpoint implements the owner's `design/landing-v2/` exports in the
existing Astro site. [Implementation and scope](../../../../docs/SITE_LANDING_V2.md)
describe the design, language coverage, accessibility adjustments and publishing
boundary. No Actions job, deployment, release or desktop runtime change is included.

`receipt.json` records the actual outcomes. `source-witness.json` binds the
production source, tests, snapshots and tokens; UTF-8 text has CRLF normalized
to LF for portable hashes. `output-witness.json` records the exact built site
and Storybook bytes. The HTTP homepage was checked against the built file.

The final ordinary site run covers 81 cases. The component run passes 294 cases
and identifies nine outdated FeatureRow snapshots: only the two inactive tone
labels changed to the new readable ink color. Those nine baselines were inspected,
deliberately updated, then passed ordinary comparisons on the same source.
Together these cover all 303 component cases. A later homepage-only opacity
change affects `.filler`, which no component story renders; the final site run
includes its rendered contrast regression check.

The original Lighthouse run caught the 24%-opacity hero filler and the small
inactive tone labels. An interrupted second attempt confirmed that `aria-hidden`
does not exempt the visible filler from contrast checks. The final implementation
uses 50% opacity, about 3.42:1, and dark small labels. Original attempt logs remain
in `logs/`; the complete failed reports and browser traces remain in the local
QA directory documented in the implementation notes. The final 21 full Lighthouse
JSON reports are preserved losslessly as `.json.gz`, with scores and timing in
`lighthouse-summary.json`. The configured thresholds were not lowered.

`screenshots/` contains the final full desktop and mobile captures. The native
alphabetic language wall retains all nineteen entries and the FAQ all ten
questions; the mobile page is consequently longer than the abbreviated reference.
Source dates and links remain visible in comparison cells. Representative docs,
language and comparison pages also received a visual review. Captures use fresh
headless contexts with media/clipboard APIs barred; no owner profile or native
desktop input is used. No external browser requests or page errors occurred.

All raw attempts are retained at
`D:/Saydraft-Codex-QA-20261112-01a1cbc7/landing-v2-20261115-r1`.
The exact local commands and actual terminal exit records are retained with the
logs. Run the normal build, content, site, component and Lighthouse commands in
`site/package.json` to produce a new qualification; this record does not qualify
future source changes or hosted publication.
