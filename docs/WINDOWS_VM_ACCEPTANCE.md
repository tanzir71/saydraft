# Disposable Windows acceptance

The owner approved **“Use a disposable Windows VM; keep host access barred”**
on 15 November 2026. This authorizes the remaining native Windows checks inside
the guest. Host microphones, audio-device discovery/playback, clipboard,
foreground queries, hooks and native input remain barred. The separate approval
for GPU identification and the local Pro benchmark does not expand those rights.

## Current state and run order

**16 November update:** the owner resumed the broader roadmap, then explicitly
stopped all VM work because of limited storage. Do not download VM tools/media,
prepare disks or provision a guest. Native acceptance stays pending; this plan
is retained for a later owner-authorized continuation. The attempted portable
QEMU download was stopped before completion; no installer ran, VM was configured
or guest was booted. Cleanup of its partial download is tracked with past builds.

No guest has been created or started. Read-only preparation found no installed
VM manager. `WHvGetCapability(HypervisorPresent)` returned success and true;
actual partition creation, acceleration and guest boot remain untested. The
optional-feature inventory alone is not evidence of a working VM.

The owner's subsequent minimum-preview instruction defers this VM work. The
Standard run was intentionally stopped at 150 completed cases / 75 pairs;
the extended Pro run was not started. These are not full latency passes.
Do not restart either matrix or provision the guest automatically to finish
the bounded preview. Keep all unexecuted native qualifications open.

After measurements, obtain supported Windows x64 evaluation or owner-provided
media from its publisher and verify its published digest. Record the edition,
build, evaluation terms, tool version and actual image hashes. Do not assume
the host license covers another installation or submit owner registration data.
Prefer a VM tool that works without changing the host. Establish actual boot
before preparing a large guest workload. No host driver/feature change, reboot,
paid license, signing or external publication follows from this checklist.

The published portable preview was built from clean `12bc27f` and independently
verified against its actual payload and embedded modules. Its artifact and hash
are in the [release publication receipt](../eval/site/results/2026-11-16-release-publication/README.md).
Bind guest results to the exact executable/package tested; later app changes
need the affected checks repeated.

## Isolation before launching Saydraft

- Use a fresh guest account, disposable disk and a unique VM identity. Retain
  the complete VM configuration and a clean pre-test snapshot.
- Disable host clipboard, drag-and-drop, shared folders, host audio backends,
  microphone/camera/USB passthrough and automatic host input capture. Do not
  mount owner profiles, credentials or unrelated disks.
- Use a headless VM and guest-only agent/control channel. Transfer an explicit
  allowlist of QA artifacts into the guest; export only the owned evidence.
  Guest input must address the guest session, never the host desktop.
- Prepare models and public reference audio before capture. An emulated or
  guest-installed virtual audio endpoint may carry public files entirely inside
  the guest. Verify that it opens no host audio endpoint. A fake Python capture
  port alone does not qualify native capture.
- Run GUI/input checks in the guest's interactive user session. A service or
  Session 0 process is insufficient. Record the guest session and desktop.
- Disconnect guest external networking before offline acceptance. Retain the
  actual network configuration and capture-time policy evidence. Model setup
  downloads remain explicit, with sizes/licenses and pause/resume.

Existing probes that require GitHub-hosted CI must not be enabled by setting
`GITHUB_ACTIONS=true`. A guest-specific entry point must independently establish
the disposable guest identity before importing native audio/input adapters.
Refusal on the owner host is required; an environment flag is not that proof.

The unexecuted [guard draft](launch/windows-vm/windows_guest_guard.py.txt) and
[test draft](launch/windows-vm/test_windows_guest_guard.py.txt) are retained for
continuation, outside active tools/tests. The proposed guest preflight requires the UUID
independently generated in the VM configuration, a matching explicit scope
manifest, a recognized virtual machine identity, the guest interactive console
and an unredirected `C:/Saydraft-QA/<vm-uuid>` directory. It performs no native
acceptance itself. Qualify it before use, then call `require_guest` before importing native test adapters;
never read this machine's UUID and use it as the expected value. Manifest scope:

```json
{
  "schema": 1,
  "owner_scope": "Use a disposable Windows VM; keep host access barred",
  "vm_uuid": "<UUID from the VM configuration>",
  "run_root": "C:/Saydraft-QA/<same UUID>",
  "host_access_barred": true
}
```

This is protection against accidental targeting, not an attestation against a
machine administrator. Sharing/network configuration still needs inspection.
Positive execution in a real guest remains pending.

## Required evidence and acceptance

Every row remains pending. Capture the original failure as well as a later
correction. Report actual results per case; do not turn an unsupported guest
feature into a pass or generalize one Windows build to every supported build.

| Cases / roadmap | Native guest check | Evidence needed |
| --- | --- | --- |
| Dictation / P2.2 | Public speech through a real guest audio endpoint into Notepad, a browser text field and a terminal fallback; verify History before insertion and the final text. | Exact app/model/audio hashes, raw/cleaned results, History timestamps and target screenshots. |
| Hotkeys / P5.1, P5.5, P6.5 | Ctrl+Win Start-menu masking, F9, hands-free chord/double tap, Esc, short-capture discard, paste-last, Scratchpad and View diff. | Guest hook/input trace, visible state changes, exactly-once delivery and absence of unintended Start-menu activation. |
| Clipboard / P5.2 | Preserve text, a copied image and rich text; exercise busy/unrenderable formats and the configured cap; inspect Win+V for dictation exclusion. | Original/restored format hashes and native history/privacy results. Memory clipboard checks do not qualify this row. |
| Refusals / P5.2–P5.3 | Password field, higher-integrity target and focus change during capture; retain recoverable text without inserting into the wrong field. | Native UIA/integrity/focus decisions and unchanged destination content. Do not record secret field text. |
| Corrections / P5.6 | Correct an inserted public term in Notepad, accept the learned suggestion, undo it and repeat with learning disabled. | Native observation, dictionary persistence and no-learning/undo results. |
| UI / P6.2–P6.4, P6.7 | Fresh-profile setup timing; keyboard-only Hub/History/Style/Notes; Bar states and pointer controls; Narrator, Windows high contrast, 200% text/display scaling and virtual mixed-DPI displays. | Timed path, guest OS settings, accessible names/focus trace and screenshots. Record any physical display/sound scope still untested. |
| Command / P7.1 | Execute the 30 instruction cases with the actual local model; review, replace, cancel and failed-replacement recovery. | Per-case validator result, native selection/clipboard restoration, target changes and fallback contents. |
| Meeting / P7.5 | At least 30 minutes of real guest capture with public speech, supported speaker tracks and the visible recording indicator; stop, analyze and save an independent Note fully offline. | Continuous duration/sample accounting, policy/indicator evidence, model/process exits, speaker transcript, summary/next steps and saved Note. Public-file execution does not establish owner speech accuracy. |
| Packaging / P8 | Launch the actual portable in the fresh guest and exercise startup, model reuse, Quit/relaunch and retained data. | Package digest, guest logs and lifecycle results. Unsigned portable checks do not qualify a signed installer. |

Owner whisper/multilingual accuracy remains deferred. Signing/distribution,
hosted SEO and the legacy-site owner decision remain separate gates in the
[handover](DELIVERY_HANDOVER.md).

## Primary provisioning references

- [QEMU Windows Hypervisor Platform backend](https://www.qemu.org/docs/master/system/whpx.html)
- [Microsoft WHvGetCapability](https://learn.microsoft.com/en-us/virtualization/api/hypervisor-platform/funcs/whvgetcapability)
- [Microsoft Windows 11 evaluation media](https://www.microsoft.com/en-us/evalcenter/evaluate-windows-11-enterprise)
- [VirtualBox guest and sharing configuration](https://docs.oracle.com/en/virtualization/virtualbox/7.2/user/working-with-vms.html)
- [VirtualBox guest-control limits](https://docs.oracle.com/en/virtualization/virtualbox/7.2/user/guestadditions.html)
