# Saydraft launch drafts

Availability refreshed 16 November 2026 against the published `12bc27f` preview.
These are owner-posted drafts. Nothing has been submitted to a listing, community,
or external repository. [GitHub presentation settings](github-settings.md) are
separate from these external submission drafts.

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
- The unsigned Windows portable preview, `v0.1.0-preview.20261116`, is public with
  its ZIP, SHA-256 checksums and build metadata. It uses source `12bc27f`, including
  the frozen insertion fix and matching app/tray branding. Broader native Windows,
  accuracy and general performance acceptance remain unqualified. The owner chose
  unsigned distribution; signing is not a requirement for this preview.
- Ask and meeting notes/speaker labels are implemented as experimental Pro
  features with explicit setup/opt-in. Broader answer/speaker/summary quality and
  full live/frozen/physical meeting acceptance remain open.

These facts come from the [README](../../readme.md), [model guide](../MODELS.md),
[privacy boundary](../PRIVACY.md), [Translate guide](../TRANSLATE.md),
[packaging guide](../PACKAGING.md) and [parity plan](../../WISPR_OFFLINE_PARITY_PLAN.md).
The [public release and landing-page verification](../../eval/site/results/2026-11-16-release-publication/README.md)
records the actual current preview, unauthenticated ZIP download and live Pages
checks. The retained earlier launch proof remains historical.

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
repositories; their maintainers decide whether to accept an unsigned preview.

Competitor names in the directory draft identify comparison categories only.
The drafts make no comparative accuracy, latency, certification or feature-parity
claim and use no competitor assets.
