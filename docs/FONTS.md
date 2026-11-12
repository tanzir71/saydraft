# Bundled fonts

P6.1's offline font foundation is implemented. Shared tokens, generated themes
and the two-theme widget gallery still follow; P6.1 acceptance stays open.

The app bundles eight original TTF files: Geist and Geist Mono (upright/italic),
Instrument Serif (regular/italic), Noto Sans Bengali and Noto Sans Arabic. Roles
prefer those script fallbacks before the system font, so Bengali/Arabic output
does not depend on Windows Nirmala. Other scripts can use system fallbacks.
No proprietary system font is redistributed.

All 18 original font/license/metadata files come unchanged from Google Fonts
revision `2e5fa2e951237b6ae65f705693d12ca76a7f78c8`. Every source byte is checked
against its declared size and upstream Git blob hash; the bundled manifest also
pins SHA-256 and immutable source URLs. Complete OFL-1.1 notices and publisher
metadata remain beside each family. Metadata and license copyright years are
preserved exactly, including the differing Noto Bengali notices. The 2,180,446
source bytes and manifest are reproduced byte-for-byte in an independent fetch.

`ui.fonts` verifies all assets before registration, then registers once per GUI
application before widgets are built. A failed face/family check retires all
newly registered IDs and preserves the previous font. Missing/corrupt resources
keep the app usable with system fonts. Successful loading changes family and
fallbacks while preserving the user's current size and weight. `role_font`
provides display/body/mono roles for upcoming theme and Hub components.

The loader has no network path and writes no system font installation. The
existing PyInstaller data collector includes all 19 files at the expected runtime
paths, with unchanged bytes. This was checked without building. Packaged build
acceptance still belongs to the safe P8 build work. Do not run the legacy build
script to test this feature.

Development-only reproduction and rendering use new output directories:

```powershell
python -m tools.fetch_font_assets --output D:\QA\Font-Reproduction
python -m tools.probe_fonts --output D:\QA\Font-Specimens
```

The fresh offscreen renderer explicitly registers only bundled fonts. Every
tested text run must resolve to its expected bundled family. It checks nonzero
glyphs for Latin, Bengali conjuncts and Arabic diacritics,
plus italic selection, monospace metrics, idempotence and custom size/weight preservation.
Its specimen image is inspected. Unit tests also cover bad manifests, altered
font bytes, missing licenses, rollback, and startup ordering. This is font
rendering evidence, not ASR accuracy, desktop-focus or model-quality acceptance.
