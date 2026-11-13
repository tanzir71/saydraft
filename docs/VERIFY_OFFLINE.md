# Verify offline operation

Install the recommended speech package through setup while connected. Finish the
explicit download and verification before disconnecting. Optional Bengali and
Arabic use the same All languages model; install it once if needed.

Turn Wi-Fi off or disconnect the network cable, then open Saydraft and dictate
into a disposable text field. Check that the local History row and pasted text
appear. Repeat with cleanup enabled only if its model/runtime is already
installed. Reconnecting must not be necessary to reuse a complete local model.
This manual check uses your microphone and field only when you choose to run it.

## Packaged Windows Firewall controls

In a local packaged installation, open Settings → Privacy. Choose **Block
Saydraft from the internet**, review the installation path and the download
restriction, then approve Windows' administrator prompt. The change takes effect
immediately; Settings Save does not create or remove a rule. Cancelling the
confirmation or the Windows prompt leaves the rule unchanged.

The fixed helper creates one enabled outbound block rule, for all profiles,
protocols and addresses, matching that installation's `Saydraft.exe`. Rule names
include a hash of the executable path. Another installation has a different
rule. Source Python and linked/remote installations cannot use these controls.
No default profile policy or unrelated rule is changed. The remove action
deletes only the matching Saydraft-managed rule; conflicting ownership,
direction, action or executable data is refused. An existing narrowed or disabled
rule is not silently repaired by Block.

Use **Check firewall rules** to inspect matching enabled rules in ActiveStore.
Then repeat the offline dictation check. A count is evidence of matching rules,
not proof that Windows Firewall is enabled or that organizational policy applies
them. Review enabled Domain/Private/Public profiles and effective policy in
Windows Defender Firewall with Advanced Security. Group Policy may disable local
rule merging. Never disable an organizational rule to make this check pass.

With the rule applied, an explicit missing-model download should fail. Network
errors explain how to remove Saydraft's block rule in Privacy and resume the
download. Installed models remain usable. After **Remove Saydraft’s block rule**
and Windows approval, retry the download explicitly. Other firewall policies or
connectivity problems can still prevent it. Update checks also need the rule
removed. A closed Settings window retires its result display; it cannot undo an
already approved helper operation. Recheck policy after an unknown result.

## Scope and evidence

The rule applies to network stacks inside `Saydraft.exe`, including native DLLs.
It does not automatically cover separate executables such as a cleanup sidecar.
An all-address rule may also affect local networking on some Windows policies;
verify installed cleanup with its loopback server before relying on that mode.
Moving the portable app changes the covered path. Review/remove its rule before
moving or uninstalling; uninstall does not silently elevate to change OS policy.

The [Python policy](PRIVACY.md) remains a separate application boundary. It
restricts Python sockets, not every native process. Neither a checkbox nor a
successful rule write establishes native-boundary acceptance. The
[dated packaged acceptance](../eval/privacy/results/2026-11-14-firewall/README.md)
retains actual native/download denial, frozen speech/History success and recovery.
Separate cleanup-helper coverage remains a distinct gate. The unit suite alone
does not establish native protection, physical dictation or owner ASR accuracy.

Implementation follows Microsoft's [program/profile rule parameters](https://learn.microsoft.com/en-us/powershell/module/netsecurity/new-netfirewallrule),
[rule removal](https://learn.microsoft.com/en-us/powershell/module/netsecurity/remove-netfirewallrule),
and [ShellExecuteEx elevation/process-handle API](https://learn.microsoft.com/en-us/windows/win32/api/shellapi/nf-shellapi-shellexecuteexw).
Provider messages and rule details are not sent to a server or shown in error
dialogs. Requests are local; no account or telemetry is added.

The separate `firewall-owned-rule-smoke` CI job blocks a newly copied Python
interpreter, tests fixed native WinHTTP and pinned model-file downloads
before/under/after the rule, and replays two real-worker dictations while blocked.
It uses only public fixture audio and memory keyboard/clipboard adapters. The
Package workflow separately exercises the frozen helper, conflicts/idempotence,
unrelated-rule preservation, frozen resource verification and public-fixture
Whisper recognition/rules/temporary History under its rule. Its native WinHTTP
and pinned model-file positive controls must work before and after removal,
and fail under the rule with download recovery guidance. These explicit probes
are reachable only through the package-verification CLI on a disposable runner.
The source probe records each read-only inspection's state, duration, return code
and safe error category, with a 30-second cold-VM query budget. The interactive
Privacy query retains its eight-second budget and reports unknown when it cannot
read policy; its timeout does not become a protection claim.
Both mutation probes refuse owner machines and self-hosted runners; neither
invokes UAC in CI. These are distinct scopes, and neither alone establishes
physical dictation or cleanup-sidecar coverage.
