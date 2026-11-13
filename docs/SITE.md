# Saydraft website

The first Astro homepage and four supporting pages are implemented in `site/`.
This is an early P9 foundation, brought forward at the owner's request. The
approved §9 tokens are shared through `design/tokens.json`; the dependency-free
generator emits CSS and light/dark Qt QSS. Qt installation and the initial gallery
are described in `docs/THEME.md`. P9's complete library, comparisons, MDX docs, demo port, schema,
launch assets and final acceptance remain open.

The current pages are Home, Download, Getting started, Privacy and Credits. The
download page discloses development status and provides actual source commands;
there are no invented installers, checksums, package-manager commands or releases.
The source instructions use the same `python -m saydraft` entrypoint as the
repository README and contributor guide.
The animated example is labeled as an illustrative simulation and never uses a
microphone. Native details/summary navigation and FAQ work without JavaScript.
The small example script respects reduced motion; React components render to
static HTML without shipping a React hydration runtime to readers.

The owner requested outer gutters around rounded color sheets and explicit
creator credit. The night/deep stack and final CTA now use the shared page gutter,
with their own internal content padding. The footer uses the owner's INTRX pattern:
"Built by tanziro.com" linking to `https://tanziro.com`, plus "Support Saydraft"
linking to `https://buymeacoffee.com/tanzir`. Both are ordinary links; no external
widget, image, script or tracking request is introduced. Browser checks cover
the panel gutters/content inset and both footer destinations at all three widths.

Button variants now retain their own foreground colors inside document pages;
the prose link rule can no longer produce dark text on a dark CTA. Focus rings
use a contrasting color for paper and dark surfaces. All 15 browser checks pass,
and 27 actual normal/hover/focus checks across the three widths confirm at least
13.27:1 text/arrow contrast and visible keyboard focus.

## Develop and verify

Use Node 24.22.2 or newer. All direct versions and transitive integrity hashes are
pinned by `site/package-lock.json`. Astro/React integration and Storybook use the
current stable versions verified at implementation time. TypeScript 6.0.3 is
intentional: the current Astro checker accepts 5/6 and rejects TypeScript 7.

```powershell
node tools/generate_tokens.mjs --check
cd site
npm ci
npm run build
npm run storybook:build
npx playwright install chromium --no-shell
npm run test
npm run lighthouse
```

For Lighthouse, set `CHROME_PATH` to the installed Chrome executable if automatic
discovery is unavailable. The same pinned Playwright Chromium works:

```powershell
$env:CHROME_PATH = node --input-type=module -e "import {chromium} from '@playwright/test'; console.log(chromium.executablePath())"
```

`npm run dev` and `npm run preview` bind to loopback. The Pages base path is
`/saydraft/`; preview the site under that path. Fontsource WOFF/WOFF2 assets are
bundled, never fetched from a font service. Full original OFL notices are served
from `public/licenses/`. Each of the five initial components has Storybook states,
with paper/night/deep decorators and reduced-motion controls. This initial set is
not the completed §9.4 library.

Playwright tests cover 390/768/1440 widths, committed Windows visual baselines,
native navigation, FAQ, the reduced-motion example, JavaScript-disabled reading,
HTML validation, local links, unique metadata/canonicals, no external page asset
requests and the 60 KB gzip JavaScript budget. Initial viewport captures are also
attached to its report. Linux users can run functional checks with a local
baseline; visual CI runs on Windows to match the committed baseline platform.

Lighthouse uses three mobile runs on Home/Download/Privacy with the planned
performance/accessibility/SEO, LCP and CLS budgets. Reports stay local or in CI
artifacts; they are never uploaded to a public temporary report service.

Initial local verification (2026-11-12): build/type diagnostics and Storybook pass;
all 15 browser checks pass against inspected phone/tablet/desktop baselines. All
nine Lighthouse runs score 100 for performance, accessibility and SEO, with zero
CLS and a maximum 960 ms LCP. Home JavaScript is 470 bytes gzip. These are local
mobile-simulation results, not a guarantee for every device or connection. The
app regression suite also passes 2213 tests with five explicit optional/native
skips; rules pass 556/556 and adversarial validation passes 100/100.

## Delivery

The owner requested automatic commits/pushes to `main` with no further PRs. All
101 earlier task PRs were closed or merged after the verified stack reached main.
The Site checks workflow builds and tests the site. Pages builds the exact
successful Site checks commit with the official Astro action, then deploys the
static artifact to GitHub Pages. Manual dispatch is also available. The canonical
is `https://tanzir71.github.io/saydraft/`; no domain purchase or analytics is added.

The previous root `index.html` and `demo/` stay intact pending the old-site
transition, so the existing Vercel project is preserved. Their planned archive
and demo port are still tracked in P9.1/P9.7. No old artifacts or model folders
were deleted to build the site. On the development PC, npm caches, dependencies,
browsers, builds and reports live on D because C has limited free space.

Framework references: [Astro React](https://docs.astro.build/en/guides/integrations-guide/react/),
[GitHub Pages deployment](https://docs.astro.build/en/guides/deploy/github/),
[Storybook React/Vite](https://storybook.js.org/docs/get-started/frameworks/react-vite).
