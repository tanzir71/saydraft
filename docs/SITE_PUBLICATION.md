# Local website publication

Build and validate the Astro site locally with `npm run content:test`,
`npm run build` and the relevant browser checks from `site/`. The generated
`site/dist/` is published to the root of the dedicated `gh-pages` branch with a
`.nojekyll` file. GitHub Pages serves that branch; no custom app or website
build/test workflow is dispatched. GitHub's own hosting service still performs
the Pages publishing step.

`main` retains the editable source, documentation and verification records.
`gh-pages` contains only generated public output. Do not publish the repository
root or owner data. A new output tree should be committed as a descendant of the
current `gh-pages` head; do not force-push it. After publishing, verify the live
homepage, download page and changelog against the local output.

The current app download is centralized in
`site/src/data/current-release.ts`. Its tag, source commit, byte size and SHA-256
must match the published GitHub asset before links are changed. Release uploads
are independent of website deployment. Keep unsigned/preview status visible and
retain the source/setup route. Historical screenshot producers are frozen beside
their captures; the current renderer may change without rewriting old provenance.

The previous custom Pages workflow is removed to keep builds local, following
the owner's instruction. App CI, packaging and draft-release workflows remain
manual-only. The public site address stays `https://tanzir71.github.io/saydraft/`.
