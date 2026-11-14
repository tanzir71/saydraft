# Saydraft launch drafts

Prepared 14 November 2026 against `8b705cc`. These are owner-posted drafts for
the current source preview. Nothing has been submitted to a listing, community,
or external repository.

| Destination | Draft |
|---|---|
| AlternativeTo and software directories | [Listing copy](alternativeto.md) |
| Product Hunt | [Name, tagline, description and maker comment](product-hunt.md) |
| Show HN | [Repository link, title and first comment](show-hn.md) |
| r/windowsapps and r/LocalLLaMA | [Separate community drafts](reddit.md) |
| Relevant awesome lists | [Target-specific entries and submission text](awesome-lists.md) |

## Verified product facts

- Windows 10/11 x64 app; source setup uses 64-bit Python 3.13.
- App code is MIT. Dependencies and model weights retain their own licenses.
- Local Parakeet/Whisper speech recognition, rules cleanup and optional local
  Qwen cleanup. Rules-only dictation needs no cleanup model.
- Default hold shortcut Ctrl+Win, hands-free capture, cancellation, History,
  Dictionary, Snippets, per-app Style, Scratchpad and Notes.
- Speech model setup requires a reviewed Download/Resume action. Installed files
  are reused. Bengali and Arabic use a shared optional multilingual speech model.
- Audio retention and app update checks default off. Speech and cleanup have no
  cloud fallback. Updates, when enabled, link to releases for manual installation.
- Translate and Command are experimental Pro features. Pro describes a hardware
  tier in this app, not a paid subscription.
- There is no published installer release. Unsigned packaging checks passed,
  while signing, release publication and broader physical Windows acceptance
  remain unfinished. Accuracy and general performance claims remain unqualified.
- Ask, meeting transcription and speaker diarization are planned features.

These facts come from the [README](../../readme.md), [model guide](../MODELS.md),
[privacy boundary](../PRIVACY.md), [Translate guide](../TRANSLATE.md),
[packaging guide](../PACKAGING.md) and [parity plan](../../WISPR_OFFLINE_PARITY_PLAN.md).
The public [release list](https://github.com/tanzir71/saydraft/releases) was empty
when checked through GitHub's release API on 14 November 2026. Refresh the
source-preview wording when publication status changes.

## Submission context

The Show HN draft links directly to runnable source, following the
[Show HN guidance](https://news.ycombinator.com/showhn.html) that people should
be able to try the project. Product Hunt's official
[launch guide](https://help.producthunt.com/en/collections/19793093-launch-guide)
is linked for the owner's final submission review. Draft fields below are copy,
not a claim about the platform's current field limits or listing acceptance.

Reddit's public rules pages did not expose the community-specific rules in this
read-only check. The Reddit drafts therefore do not claim posting permission.
Awesome-list targets and entry formats were inspected in their primary
repositories; their maintainers decide whether to accept a source preview.

Competitor names in the directory draft identify comparison categories only.
The drafts make no comparative accuracy, latency, certification or feature-parity
claim and use no competitor assets.
