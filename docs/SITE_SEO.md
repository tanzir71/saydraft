# Website metadata and discovery

The static build generates 46 HTML pages: 44 indexable routes, a noindex prepared-example demo
and a custom 404.
Every page gets its own 1200×630 PNG social preview, plus a separate 1280×640
GitHub social-preview image. Titles and descriptions come from the rendered
page, using the approved paper/ink tokens and pinned local Instrument Serif,
Geist and Geist Mono fonts. Satori embeds font outlines before Sharp rasterizes
the result. No browser, system font or external font/image request is needed.
The build refuses filename collisions, clipped content and overlapping text.

The shared head supplies canonical, OG image/size/alt and large-image Twitter
metadata. A build manifest records page/image hashes and text bounds. The custom
404 offers Home/Docs/Download recovery and `noindex,follow`. It is omitted from
the sitemap, readable-page directory and indexing payload.

## Structured data and current eligibility

Home, Download and the offline pillar share one SoftwareApplication identity,
the actual app source version, Windows 10/11, UtilitiesApplication, free offer,
MIT license and setup URL. All nineteen highlighted speech choices are included.
Language WebPages refer to this identity. Home and dated content emit FAQPage
data from their actual questions; the build requires every structured question
and answer to match its rendered native FAQ. Docs retain breadcrumbs. Credits
has a visible Tanzir Rahman link and matching Person data.

These descriptive objects are separate from Google's current rich-result gates:

- Google requires a genuine review or aggregate rating for a software-app rich
  result. The site has neither. Tests, stars and download counts are not ratings.
  [Software-app requirements](https://developers.google.com/search/docs/appearance/structured-data/software-app).
- Google retired FAQ rich results on 7 May 2026 and removed their documentation
  on 15 June. Useful visible FAQs and matching schema remain, but the original
  plan's Google FAQ rich-result acceptance is obsolete.
  [Google's dated updates](https://developers.google.com/search/updates#june-2026).
- `downloadUrl` means a binary download. The older public unsigned verification
  pre-release predates current source, so it is not advertised as this version's
  binary. The schema uses the real source-setup `installUrl` and omits a current
  binary URL. [Schema.org definition](https://schema.org/SoftwareApplication).

Real code submissions of the built Home, Download and offline pillar to Google's
Rich Results Test each returned **Something went wrong / Log in and try again**.
The inputs, hashes and screenshots are retained locally. No external test pass,
Google account verification or rich-result display is claimed. P9.5 remains open
at its original external acceptance scope; local contracts do not replace it.

## Sitemap and crawler files

`@astrojs/sitemap` generates `sitemap-index.xml` and its child sitemap. The build
compares the generated URLs against every actual indexable HTML page and the
public route catalog. The existing `sitemap.xml` remains a compatible URL list.
All three must agree exactly. The shared head links to the sitemap index.

`robots.txt` includes its absolute sitemap URL. At the current project URL,
Google uses **https://tanzir71.github.io/robots.txt**, not the copy under
`/saydraft/`. The project copy is informational until it is served at a host
root; it does not establish an effective crawling policy for this Pages project.
An owner-controlled host-root policy can include the sitemap line below, merged
with any existing rules. No sibling repository or custom domain is modified.
[Google's location rule](https://developers.google.com/crawling/docs/robots-txt/create-robots-txt).

```text
Sitemap: https://tanzir71.github.io/saydraft/sitemap-index.xml
```

`llms.txt` links to clean Markdown exports of all 44 indexable pages.
`llms-full.txt` contains the complete readable content. The exports preserve
commands, source links, checked dates, model tables, native-language text and
collapsed FAQ answers, while omitting navigation, forms and scripts. These are
agent documentation aids, with no search-ranking claim. The current
[llms.txt proposal](https://llmstxt.org/) allows subpath files; Google's
[AI guidance](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide)
states that these files do not improve or harm Google Search visibility.

## Owner verification and IndexNow

Copy `site/.env.example` to the ignored `site/.env`, then fill the **token values**
from the owner's Google Search Console and Bing Webmaster Tools. Do not paste
the full HTML tag. `GOOGLE_SITE_VERIFICATION` supplies Google's public ownership
meta value; `BING_SITE_VERIFICATION` supplies Bing's 32-character hexadecimal
`msvalidate.01` value. Empty values produce no tag; malformed values fail the build.
The retained manual Pages workflow also maps repository variables with these
names into its build. No account has been verified by this source change.

Local checks run real builds with a malformed token (refused), synthetic valid
formats (tags checked on all 44 pages), then empty defaults (tags absent again).
Synthetic format checks do not claim ownership of a search-console property.
After hosting publication, the owner can verify the URL-prefix property
`https://tanzir71.github.io/saydraft/` and submit its sitemap index.

A stable public UTF-8 key file is in `site/public/`. The generated `indexnow.json`
contains the exact 43 URLs, host without a path, and an explicit `keyLocation`
under `/saydraft/`. The protocol permits that subpath key for URLs below the
same path. The key file must be publicly reachable before a notification is
submitted; a successful submission proves receipt, not indexing.
[IndexNow protocol](https://www.indexnow.org/documentation).
The build sends no notification. The payload is prepared for owner review after
deployment, and no indexing, account or hosting operation is automated here.

## Local verification

Run the website commands in [SITE.md](SITE.md). The fourteen Node contracts cover
existing date/release/HTML/model behavior plus path safety, token formats,
readable HTML exports and real local-font rasterization with intact pixel gutters.
Browser checks verify every page-specific image and its PNG dimensions, matching
metadata, current-version/visible FAQ data, author credit, all readable exports,
the exact sitemap/IndexNow payload and no-JavaScript 404 recovery at three widths.
Existing component and Home baselines remain ordinary comparisons.

No app runtime, model pins, desktop/audio/input, owner clipboard, reserved
accuracy recordings, release or PR is involved. All five workflows remain
manual-only. Hosted publication, genuine review/rating evidence, account/root-host
setup and the original Rich Results acceptance remain separate outstanding work.

The [15 November evidence](../eval/site/results/2026-11-15-seo/) qualifies the
implementation at `88bf345`: 54 site checks, 234 component checks, fourteen Node
contracts, clean 91-file type diagnostics and successful static/Storybook builds.
All 21 Lighthouse runs score 100 for performance, accessibility and SEO, with
maximum LCP 960 ms and zero CLS. The 164 static output files match the tested
bytes. All 45 generated previews and 43 readable exports are retained alongside
the original failures, Google login-status screenshots and token-build receipts.
The verifier checks 375 source files and 165 evidence records, and can compare
every actual static/Storybook output file. These are local implementation checks;
they do not accept P9.5's outstanding external conditions.
