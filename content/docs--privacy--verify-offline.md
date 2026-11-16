# Verify Saydraft Offline — Network and Firewall Checks

Canonical: https://tanzir71.github.io/saydraft/docs/privacy/verify-offline/

Check local Saydraft dictation without internet, understand its Python network guard, and review optional packaged Windows Firewall controls and limits.

Facts checked: 2026-11-14

## Prepare while connected

 

Finish the explicit download and verification of your selected speech models. Install cleanup or experimental feature dependencies too if you plan to use them offline. Review [model requirements](https://tanzir71.github.io/saydraft/docs/models/) and keep optional update checking off if you do not want release requests.

 

## Try an ordinary offline draft

 

- Disconnect Wi-Fi or the network cable.
 
- Open Saydraft and an ordinary editable text field.
 
- Dictate a short sentence and review both the local History entry and delivery.
 
- Repeat with optional cleanup only if its model/runtime is already installed.

 

This manual check uses your microphone and chosen field only when you run it. Reconnecting should not be needed to reuse complete compatible local files. Missing files require a separate explicit setup action when connected.

 

## Inspect connections

 

Windows Resource Monitor can show process connections while you dictate. A local cleanup server may appear as a loopback connection. Read the [privacy page](https://tanzir71.github.io/saydraft/privacy/) for explicit downloads, saved opt-in release checks, retained audio and clipboard boundaries.

 

The Python network guard restricts Python sockets and scoped download/update exceptions. It does not prove that every native library or separate process is blocked. Observing no traffic in a short session also does not prove every path.

 

## Optional packaged Firewall controls

 

For a local packaged installation, Settings → Privacy offers Block Saydraft from the internet. Review the executable path and download restriction, then approve the separate Windows administrator prompt if you choose to proceed. The operation takes effect separately from Settings Save. Cancelling leaves the rule unchanged. These controls are unavailable for a source Python process or a linked/remote installation.

 

Check firewall rules inspects matching enabled rules. A count is evidence of those rules, not proof that Firewall profiles are enabled or organizational policy applies them. Review effective policy in Windows Defender Firewall with Advanced Security. Keep organizational rules intact.

 

## Recheck downloads, cleanup and the path

 

A matching effective block should stop an explicit missing-model download with guidance to remove Saydraft’s block rule and resume. Installed speech files remain available. After Remove Saydraft’s block rule and Windows approval, retry the download explicitly; other connectivity or policy can still prevent it.

 

The rule covers native stacks within that `Saydraft.exe`, not separate helpers such as the cleanup sidecar. All-address rules can affect loopback on some policies, so check installed cleanup before relying on it. Moving a portable app changes the path covered by the rule. Review/remove its rule before moving or uninstalling; uninstall does not silently elevate to change OS policy.

 

The linked implementation record documents a narrow packaged speech/download test. It is separate from broad owner accuracy, physical dictation and complete cleanup-helper coverage.

## A few useful answers.

### Will a Firewall block stop setup downloads?

Yes, a matching effective block can prevent model downloads and update checks. Installed files remain local. Remove Saydraft's own block rule with Windows approval before explicitly resuming a download.

### Does Saydraft's rule cover every helper process?

No. The rule is tied to the packaged Saydraft.exe path. Separate executables such as the cleanup sidecar require their own effective-policy consideration. Moving the portable app changes the covered path.

## Sources and further reading

- [Offline verification, packaged rules and native scope ↗](https://github.com/tanzir71/saydraft/blob/main/docs/VERIFY_OFFLINE.md)

- [Python networking and explicit exceptions ↗](https://github.com/tanzir71/saydraft/blob/main/docs/PRIVACY.md)
