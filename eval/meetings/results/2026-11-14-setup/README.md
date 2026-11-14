# Meeting setup: local verification

Clean implementation source: `4d497584093a63fd00c3c01db50d7daef4633a49`.
Delivery uses local validation and direct pushes; no Actions run was dispatched.

The final guarded run passes **661 tests**, with one profile/instance entry-point
test deselected. The runner bars real SoundCard/sounddevice imports and owner
profile services, uses fresh disposable paths and injects fake device/model ports.
The receipt fingerprints 493 Python files before/after the run. It does not claim
that all repository tests or the live OS/input matrix ran.

Sixteen owned offscreen renders cover light/dark, 16/22px text, 460/768px actual widths
and model/device views. Start, consent and horizontal bounds pass. The setup
checks include explicit model review/download/pause/reinspection, device Refresh,
exact endpoints, fresh permission, stale Settings refusal, the painted indicator,
Auto multilingual retry, recovery without recapture and independent Notes.
Two native-object lifetime fixtures cover metadata failure before COM teardown.
Rules pass 556/556 and authored adversarial validation passes 100/100.

The clean-source fresh-environment **portable bundle** passes frozen imports,
resources, model/font/license notices, capture headers, Python NetworkGuard and
the module/file audit. All four setup modules occur in its Analysis table. It
uses no audio devices, clipboard, foreground reads, hooks or ASR. The portable
ZIP and full build remain local; their hashes are retained. `-SkipInstaller`
means the installer and packaging acceptance gates remain **false**. No install,
signing, publication, native firewall or connected frozen meeting was accepted.

The first local build compiled but failed QtWidgets import. PyInstaller copied
an incompatible `icuuc.dll` from the desktop launcher's inherited PATH; 20 exports
required by QtCore were absent. A separate copied-bundle diagnostic removed only
that copied DLL and passed verification. The original failed bundle/report remain
unchanged. The corrected builder restricts PATH to explicit Python/Git and Windows
directories, restores the environment afterward, and the fresh second build passes.
Its native-origin record contains no WindowsApps binaries. Shared pip caching
reuses wheels while retaining a fresh venv and output directory.

Earlier check logs remain intact: r01 had two test-assumption errors; r02 exposed
silence handling and a missing Pro fixture setting; r03 passed 125. r04 retained
the barred profile/instance entry-point failure; r05 reused a disposable cache
and failed 16 cache-state assertions. Per-run profiles fix that harness problem.
r06/r07 pass 636; r08 referenced an absent test file and ran no tests; r09 passes
16 endpoint checks; r10 passes 23 packaging contracts. r11 is the final 661 pass.

Run the standard-library verifier from a checkout containing this source:

```powershell
python eval/meetings/results/2026-11-14-setup/verify-setup.py.txt --repo .
```

Optionally add `--build-root PATH` to hash the local ZIP and check its Analysis
table. The verifier never imports the app, SDKs or models. `files.json` retains
the exact raw-record hashes. Live/default-profile capture, broad language/speaker/
summary accuracy, a connected frozen workflow and the 30-minute meeting gate
remain open; P7.5 is unchecked.

Eight new files had mixed CRLF/LF bytes in the tested Windows checkout. The initial
verifier accepted only uniform line endings and failed. Their exact tested bytes
are retained under source-bytes: each must match its original test fingerprint
and differ from the Git blob only by CRLF normalization. Both verifier versions
and the original manifest remain retained; product/test outputs were not edited.

The second verifier still expected the requested 780px width. Qt correctly capped
it to the 768px available offscreen area; the original render report already
records 768px. The verifier now checks those actual dimensions. Images and
render records are unchanged; the second verifier is retained too.
