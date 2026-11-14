# Website component library

The complete §9.4 library has 23 React components and 71 Storybook states. The
three documentation parts count separately. Each component uses CSS Modules,
the shared approved tokens and the bundled fonts. Import components directly
from their folders under `site/src/components/`.

| Component | States and purpose |
| --- | --- |
| NavPill | Desktop links, native mobile menu closed/open |
| Button | Primary, secondary, on-dark |
| Eyebrow | Paper and dark text |
| SerifHeading | Medium, large, hero, dark; semantic heading tag and emphasis |
| Sheet | Paper, raised, night, deep, stacked edges and overlap; outer gutters and inner padding |
| Ribbon | Animated SVG text path, static and reduced-motion versions; unique path IDs |
| BarDemo | Idle, listening, cleaning, inserted, reduced motion |
| EditChip | Backtrack, hesitation removal, dark surface |
| BeforeAfterCard | Backtrack, fillers, lists, retained Bengali/Arabic example |
| FeatureRow | Visual left/right, highlighted, reduced motion; CSS scroll highlight |
| StyleSwitcher | Formal, Casual, Very casual, independent instances |
| KeyCaps | Hold, hands-free, paste-last, dark surface |
| StatBlock | Qualitative, sourced/date-stamped, dark; no invented speed figures |
| PrivacyFacts | Paper/dark; explicit downloads and default-off update checks |
| CompareTable | Date/source on every cell; named keyboard-scrollable region |
| FAQ | Closed, open, dark; native details/summary |
| DownloadCard | Development, illustrative future release, no package command, dark |
| CreditsBand | Open-model text credits with an ordinary credits link |
| Footer | Product/comparison links and the owner's creator/support links |
| AnnouncementBar | Linked or text-only development notice |
| TableOfContents | Section links, nested heading indentation, dark surface |
| Callout | Information, warning, dark surface |
| CodeBlock | Commands, long scrolling line, dark surface; explicit Copy and feedback |

The global Storybook toolbar selects paper/night/deep and full/reduced motion.
The full-bleed layout stories retain the same page gutters as the real site.
Visual baselines cover every story at 390, 768 and 1440 pixels: 213 PNGs in
`site/component-tests/library.spec.ts-snapshots/`. Home has three separate
integration baselines in the existing site test suite.

## Static behavior and composition

Astro renders React to HTML. The tone switcher uses labelled native radios and
CSS, FAQ/navigation use native disclosures, and the ribbon has a static visual
under the system or Storybook reduced-motion preference. No React hydration
runtime is needed by these components on the public pages. The installed Astro
React renderer gives separate roots unique identifier prefixes.

When composing framework components from an Astro page, pass rendered content
through a named slot rather than an inline JSX object prop. The Home feature
row uses `<div slot="visual"><StyleSwitcher ... /></div>`; React callers use
the regular `visual` ReactNode prop. See the [Astro framework component guide](https://docs.astro.build/en/guides/framework-components/).

`Base.astro` installs the small shared copy handler once. It handles a deliberate
button click, writes only the displayed public command, never reads clipboard
data, and reports denied/unavailable access with a manual-selection fallback.
Late results do not update detached elements. Storybook uses the same handler.
Without JavaScript, source commands remain visible and selectable; tone controls,
FAQ, mobile navigation and guide contents links still work.

Home consumes the ribbon, chips, model credits, keycaps and tone feature row.
Every page uses the shared footer. Download consumes CodeBlock and the development
DownloadCard. Dated guides derive their contents links from the rendered MDX
heading IDs. Creator credit remains “Built by tanziro.com”, with the existing
support link; neither link embeds an external widget.

## Release and factual data

The public Download page passes no release object and advertises no unpublished
installer or package-manager command. A future `DownloadRelease` must provide
its actual version, URL, positive exact byte size, complete SHA-256 and a status
note. A package command is optional. Invalid byte/hash data refuses rendering.
The future-release Storybook fixture is visibly labelled as an illustration and
is imported only by stories. It is not release metadata or a published artifact.

Comparison cells require source links and checked dates. The supplied story
compares current local model setup using repository documentation. StatBlock
supports qualitative copy as well as sourced figures; the library adds no speed
or accuracy claim. Broader language and owner accuracy acceptance remain separate.

## Local verification

```powershell
cd site
npm run content:test
npm run build
npm run storybook:build
npm run test:components
npm run test
npm run lighthouse
```

The component browser checks cover all 71 states at three widths, page overflow,
local-only requests, browser errors, text contrast on the flat token surfaces,
native keyboard tone selection, independent radio groups, copy success/denial,
download/checksum disclosure, keyboard table scrolling and full/reduced motion.
Clipboard cases replace the browser API with an in-memory port; they neither
read nor write the owner's clipboard. These headless checks use no microphone,
audio device, foreground inspection or OS input.

Astro and React serialize valid HTML5 void/boolean attributes differently. The
validator permits both formatting styles, while retaining structural, duplicate
ID and ARIA rules. Negative contract checks still reject self-closing non-void
content, duplicate IDs and ARIA naming misuse. The two formatting rules describe
the allowed alternatives: [void-style](https://html-validate.org/rules/void-style.html)
and [attribute-boolean-style](https://html-validate.org/rules/attribute-boolean-style.html).

Default ports remain 4173 (site), 6006 (Storybook) and 4174 (Lighthouse).
If another project owns them, set `SAYDRAFT_TEST_PORT`,
`SAYDRAFT_STORYBOOK_PORT` and `SAYDRAFT_LIGHTHOUSE_PORT` to unused local ports.
The checks refuse reusing an existing server. They never stop another project's
process. On the development PC, dependencies, browsers, output and reports stay
on D:. The current five GitHub workflows remain manual-only; these commands
require no Actions run or PR.

The [15 November qualification](../eval/site/results/2026-11-15-components/)
retains the final 234 component and 30 site results, seven Node contracts, clean
build/type checks and all fifteen Lighthouse reports. Minimum performance is 99,
accessibility/SEO 100, maximum LCP 960 ms, and CLS zero. The rebuilt site's output
is byte-identical to the Lighthouse-tested output. Its standard-library verifier
checks the committed source and snapshots, raw reports and optional actual build
directories. This accepts P9.2; the other original website milestones and hosted
publication remain open.
