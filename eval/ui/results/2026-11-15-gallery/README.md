# Public desktop gallery qualification — 15 November 2026

Clean source **c5428286dfac1133f1a6d08b67656f3ddba578a9** completes the named
P6.6 component-gallery scope. Five tests pass in 79.19 seconds, with no skips:

```powershell
python -m pytest tests/test_gallery.py tests/test_bar_gallery.py tests/test_gallery_catalog.py -m gallery -q
python eval/ui/results/2026-11-15-gallery/scripts/verify.py.txt --repo . --check-current
```

The retained runner applies the earlier owner-I/O guard before app imports.
Explicit installed Qt/dependency library paths remain available to fresh children;
user data profiles remain isolated. Only those three named files were collected.
The actual parent tool session exited zero; each renderer's subprocess exit is
observed by the tests. This is not a held Windows Job/process-tree qualification
or a full-app test run.

`scale-1` and `scale-2` contain **336 actual PNGs**: 328 catalog views (82 scenes
× two themes × two densities) plus eight Controls/Style views. All catalog decoded
pixels match the reviewed source baselines. Tests additionally compare the four
original baseline PNGs, check all actual Bar enums, inspect guard receipts and
exercise live selection, palette refresh and fixture cleanup. The separately
existing Bar gallery tests also pass at both densities; their reports are retained.

The 115 Git source/resource/fixture witnesses bind this record to its original
source. The stdlib verifier checks record integrity, source objects, all snapshot
inventory/digests/dimensions, clean renderer source, guards and JUnit results.
It reads files; it does not rerender, infer or access owner ports. `--check-current`
also refuses changed relevant source/fixtures. Historical verification remains
available without that flag.

Original diagnostics are unchanged:

- The first live test found that a SQLite fixture transaction context did not
  close its connection. Explicit `closing()` fixes it; the focused rerun and final
  suite require the disposable directory to disappear.
- The first complete attempt passed the live test but four fresh children could
  not import Qt after APPDATA isolation. The runner now passes the known installed
  library path explicitly; no privacy guard was relaxed and no profile reused.
- An additional subprocess audit initially rejected CPython's Windows string
  form of the two Git provenance commands. The corrected guard admits only the
  exact list/string forms of those same commands. The refused exports remain
  diagnostics and receive no successful qualification credit.

Progress, readiness, microphone levels and practice text are public view fixtures.
These pictures do not prove model installation, ASR, clipboard privacy, physical
Windows input, Narrator, mixed-DPI or onboarding speed. The recorded guards show
no owner/device/audio/clipboard/input access, no blocked attempts in the accepted
renderers and no imported model SDKs. Only Git provenance commands are spawned.

The file-only package inspection finds neither gallery module in the actual
existing EXE's embedded PYZ. Only the two developer-gallery Python files changed
since the preceding delivery. The f6cd0bf portable keeps its original source and
qualification; no rebuilt executable or release is claimed. All critical release
acceptance remains open in [the handover](../../../../docs/DELIVERY_HANDOVER.md).
