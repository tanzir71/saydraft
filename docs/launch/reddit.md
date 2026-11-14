# Reddit drafts

Verified 14 November 2026. See the [shared facts and publication status](README.md).
These are separate drafts for the owner to review against each community's
current rules; no post has been made.

## r/windowsapps

Title: Saydraft: an open-source local dictation app for Windows (source preview)

I'm the developer of Saydraft, a Windows tray app for local voice dictation.
Hold Ctrl+Win, speak and release to recognize speech, clean the text and attempt
delivery into your original text field. History saves the result before delivery.

It uses installed Parakeet or Whisper models and can run with rules cleanup
alone. Optional AI cleanup runs locally too. The Hub includes History,
Dictionary terms, Snippets, per-app Style, Scratchpad and Notes. Model downloads
are explicit and resumable; audio retention and app update checks default off.

This is a free MIT source preview for Windows 10/11 x64. The README has Python
3.13 setup instructions. A published installer, signing and broader Windows
acceptance are still in progress. Experimental Pro features are hardware-gated,
not a paid subscription tier.

Project and setup: https://github.com/tanzir71/saydraft

I'd welcome feedback on installation and dictation recovery workflows.

Community reference: [r/windowsapps rules](https://www.reddit.com/r/windowsapps/about/rules/).

## r/LocalLLaMA

Title: Saydraft: Windows dictation with local Parakeet/Whisper and optional Qwen cleanup

I'm building Saydraft, an MIT Windows dictation app. Recognition runs locally
with Parakeet or Whisper. Rules cleanup works without an LLM; the optional local
cleanup path uses pinned Qwen3.5 0.8B/2B weights with llama.cpp on CPU or Vulkan.
Experimental Command and Translate share a separate explicitly installed 4B model.

The pipeline saves History before attempting guarded delivery into the original
field. Model replies pass mechanical validation, and normal cleanup can keep the
rules result when the model is unavailable, out of budget or rejected. Speech and
cleanup have no cloud fallback. Model downloads and optional update notices are
separate explicit controls.

Source and setup: https://github.com/tanzir71/saydraft

It is currently a source preview for Windows 10/11 x64 with Python 3.13, not a
published installer release. The repository retains benchmarks and their limits;
I am not claiming cloud-equivalent accuracy or that general latency targets have
been met. Model licenses apply separately from the MIT app code.

I'd be interested in feedback on local cleanup validation and failure recovery.

Community reference: [r/LocalLLaMA rules](https://www.reddit.com/r/LocalLLaMA/about/rules/).
