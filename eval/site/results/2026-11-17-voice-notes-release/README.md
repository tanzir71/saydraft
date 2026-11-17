# Published 0.1.1 download and voice-note guidance

App source: `dcfab880d1896f1fbdb32be7e34387c2b46b0ad5`.
Website source: `ef5ef10ee228797c77b1c6c34abbabed39297fd9`.
Generated Pages commit: `426e360b7309919bf70ebe0bd46617fef2829243`, a regular
descendant of the existing `gh-pages` branch. The publisher preserves/restores
the main index and pushes the locally generated static build without force.
No custom workflow was dispatched or Pages configuration changed.

[Live download](https://tanzir71.github.io/saydraft/download/) and
[release](https://github.com/tanzir71/saydraft/releases/tag/v0.1.1-preview.20261117)
use the verified unsigned 0.1.1 ZIP. The shared release record pins its actual
157,322,503-byte size and SHA-256. README, setup/download and changelog links
point to it. Notes and shortcut guides describe F10 start/stop, the visible
Record note button, local Notes/History saving and recovery. Notes FAQ metadata
also includes the shortcut. Model-download behavior remains the explicit setup
choice approved by the owner.

Local content tests pass **19/19**. The final static build has zero Astro errors
and produces 46 pages / 44 indexable URLs, local social previews and readable
exports. Six release browser checks pass across mobile, tablet and desktop:
landing CTA destinations, portable instructions, exact byte count/SHA and current
changelog link. The final subsequent rebuild adds the shortcut-guide text; the
tested release manifest/components are unchanged.

Unauthenticated live verification compares Home, Download, Changelog and Notes
HTML against the local generated files, allowing only CRLF/LF normalization.
All match. Three CSS/font assets return 200 and match local bytes. The separate
[portable record](../../../ui/results/2026-11-17-voice-notes-portable/README.md)
retains the full public ZIP/checksum/metadata streaming hashes. A further
independent Git-blob check verifies all 132 immutable cleanup, behavior and
portable evidence objects and archived members, including original failures.
`manifest.json` pins the raw receipts/producers in this directory. No indexing
submission, analytics setup, VM work or host audio/input access was performed.
