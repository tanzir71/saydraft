# Working Windows preview and public download links · 16 November 2026

The owner confirmed the latest app is working and requested publication. The
unsigned development pre-release is public at
[v0.1.0-preview.20261116](https://github.com/tanzir71/saydraft/releases/tag/v0.1.0-preview.20261116).
It contains the unchanged working ZIP, SHA256SUMS and BUILD_INFO.json.
Tag source: `12bc27ffdb3ba388ea199e5e51661c968815c2fe`.
ZIP: 157,308,167 bytes; SHA-256:
`b24ca638e91035c35029b67577b7d62859e22904618a9fa7e982a330ec40901f`.
The uploaded GitHub digest and a fresh unauthenticated public download both
match that artifact. No binary was rebuilt or retagged to a different source.

Website source: `b41509817a9d402a42cae4c9097fba0617f3069e`.
Generated Pages commit: `2ce5c11b8412f00ef1795734368fd31b6a378983`.
The announcement, navigation, hero and final CTA now link to the actual ZIP.
The download page includes size, checksum, unsigned status, release notes and
portable setup. README, getting-started, content CTAs, SoftwareApplication metadata
and changelog agree with the published preview. Nineteen language guides and
creator credit are preserved.

The site was built locally and its 171 generated files pushed to `gh-pages`
with `.nojekyll`. Pages serves that branch. The prior custom Pages workflow was
removed; no custom build/test workflow was dispatched. GitHub's managed Pages
publishing completed successfully. [Repeat-publication procedure](../../../../docs/SITE_PUBLICATION.md).

Verification:

- All 19 content tests pass, and Astro type-check/build produces 46 pages,
  44 indexable URLs and the generated SEO assets/exports.
- Eighteen scoped browser cases pass across mobile, tablet and desktop: release
  links, checksums, current changelog, SoftwareApplication/FAQ data, all public
  local links/metadata, source-copy controls and the landing layout/accessibility.
- Live homepage, download and changelog return 200, include the current preview
  and exactly match the committed Pages HTML. They match the local build after
  Git LF normalization. Four public font/CSS assets also return 200.
- React review confirms static shared release data, semantic accessible anchors,
  no added client fetch/hydration, hooks, dependencies or external page-load resources.

Original failures are retained. An old screenshot check incorrectly compared a
historical capture's producer hash with the subsequently changed renderer. The
exact original renderer from `e0b65c7` is now frozen beside those captures and
matches the original hash; no image hash was replaced. Other failed browser
assertions still expected an absent binary download or the old announcement.
Those expectations were updated for the published release and their cases pass.
The first live check predates Pages propagation; final checks confirm publication.

These results do not expand the app's native or all-language accuracy acceptance.
The owner confirmation covers the reported working insertion flow. Distribution
remains an unsigned portable development preview. Historical installer/signing
gates and earlier evidence remain unchanged.
