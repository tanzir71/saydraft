# Dated website documentation

The website has 43 public HTML routes. Twenty-two MDX pages cover five
comparisons, the offline pillar, developer workflows, changelog, eleven docs
routes (including their index), Download, Privacy and Credits. The nineteen
alphabetically ordered language pages and their overview retain their existing
routes and model-coverage limits.

## Routes and content

`site/src/content/docs/` contains Getting started, Shortcuts, Styles, Dictionary,
Local models, Languages, Command Mode, Verify offline, Troubleshooting, FAQ and
the docs index. Verify offline uses the nested `privacy/verify-offline.mdx` path.
`site/src/content/pages/` contains Download, Privacy and Credits, replacing their
previous Astro files. The shared `Content.astro` layout supplies visible checked
dates, sources, breadcrumbs, contents, optional native FAQs, related links and
the existing readable CTA. Docs also get a current-page navigation marker.

The explicit route catalog in `data/guides.ts` combines guide, docs and resource
catalogs. `[...content].astro` refuses missing, duplicate or unlisted entries.
The same catalog feeds the public-page list and sitemap; no slug convention
silently decides a collection. Titles, descriptions and headings are required,
and an optional emphasized phrase must be an exact heading suffix.

The build checks every nested MDX date before content-cache reuse, then checks
again in the collection schema. The existing 120-day UTC window still rejects
missing, invalid, future and stale dates. Changing a date requires source review.
The changelog continues to fetch published GitHub releases only at build time;
readers do not request the API, and unpublished artifacts are not advertised.

## Model sizes and factual limits

Download and Local models calculate transfers from the actual pinned app
manifest at build time. Dependencies are deduplicated, and bundled notices do
not count as network bytes. The default speech model plus language detector is
773.4 decimal MB; optional GTCRN is 0.54 MB. Installed/temporary disk usage is
separate. Eight speech/package choices and five optional editing/runtime choices
link to their catalog sources and disclose their licenses.

The user guides distinguish recognition coverage from measured accuracy,
Brazilian Portuguese from a separate decoder, quiet-speech Whisper mode from
Whisper ASR, language pins from download actions, and the Python network guard
from native or separate-helper enforcement. Experimental editing remains
default-off with reviewed setup. Command clipboard fallback has its own opt-in;
Windows clipboard history/sync is outside the app's restoration guarantee.
The owner accuracy acceptance and known Bengali/Tamil/Telugu errors remain
visible. No reserved accuracy recordings were used for this documentation work.

Credits links to the full notices and original self-hosted OFL license texts.
It retains original-model/conversion, adapted wordfreq data and software credits.
The root third-party notice now correctly labels the 4B model as experimental
editing rather than an unselected developer candidate. That bundled-resource
change requires a fresh clean-source portable build; runtime code and model
pins are unchanged.

## Local verification

Run the commands in [SITE.md](SITE.md) and [SITE_COMPONENTS.md](SITE_COMPONENTS.md).
`npm run content:test` includes three model-transfer contracts alongside the
date, release and HTML contracts. The site checks require unique metadata and
one unique H1 on every public route, validate all built HTML and internal links,
and check the exact sitemap. Additional docs checks cover all dated resources,
all eleven docs without JavaScript, nested keyboard navigation, nineteen
language/model rows and the five original OFL notices at 390/768/1440 widths.
Copy cases use an in-memory browser API. No owner clipboard, profile, microphone,
foreground inspection or native input is used.

Ordinary component checks retain the 213 committed component baselines and three
Home baselines. Lighthouse now includes Local models and nested Verify offline
alongside its previous five URLs, with three runs per URL and unchanged budgets.
Actual stale-date builds for a nested doc and a migrated resource must fail;
the probe restores exact source bytes afterward.

All five GitHub workflows remain manual-only. Local results and direct source
pushes do not imply a new hosting deployment, public release, signed installer,
owner accuracy acceptance or completion of the full implementation plan.

The [15 November qualification](../eval/site/results/2026-11-15-docs/) accepts
P9.4 at source `5848e53`: all 42 site, 234 component and ten Node checks pass,
with zero diagnostics across 82 checked files, 43 built pages and a successful
Storybook build. All 21 Lighthouse runs score 100 for performance, accessibility
and SEO, with maximum LCP 960 ms and zero CLS. Actual output hashes match the
tested site. Both real stale-date builds fail and restore exact original bytes.

The fresh clean-source portable has 1,384 files. Its complete frozen checks and
bundle audit pass, including the corrected bundled notices. The retained verifier
checks all 362 source witnesses and 82 evidence records, and can additionally
verify every actual static/Storybook file, bundle file and ZIP entry. The unsigned
portable qualification does not accept the unbuilt installer or release gates.
