# Bundled desktop fonts

App UI v2 uses Geist for body text, Familjen Grotesk for display headings,
Martian Mono for labels/code and Doto for numeric readouts. Noto Sans Bengali
and Noto Sans Arabic remain bundled script fallbacks. Other scripts use system
fallbacks; no proprietary system font is redistributed.

The manifest lists **20 original files: eight TTF faces, six complete OFL notices
and six publisher metadata files**. All bytes come unchanged from Google Fonts
revision `2e5fa2e951237b6ae65f705693d12ca76a7f78c8`. Size, Git blob identity and
SHA-256 are verified before registration. Full notices stay beside each family.
The package collector includes only manifest-listed fonts; older reference faces
can remain in the checkout without being shipped in the app.

The loader registers once per GUI application. Failed registration rolls back
all newly registered IDs and preserves the previous app font. There is no
network path or system font installation. Family selection preserves the live
application size and weight. The approved theme minimum is 14px; role sizes
use ratios of the current body font. Explicit pixel sizes remain authoritative
when QFontInfo cannot resolve an unavailable fallback face.

```powershell
python -m tools.fetch_font_assets --output D:\QA\Font-Reproduction
python -m tools.probe_fonts --output D:\QA\Font-Specimens
```

The fresh offscreen probe checks registered families, missing glyphs for Latin,
Bengali and Arabic, Doto readouts, italic selection, monospace metrics,
idempotence and size/weight preservation. Tests reject changed bytes, missing
licenses and invalid manifests. This verifies typography, not speech accuracy
or native Windows acceptance. See [the v2 implementation notes](APP_UI_V2.md).
