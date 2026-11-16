# Preview availability documentation

Source `2b35256a722de32be5b22bb5db6e964f7d593bd7` corrects the source-only copy on
the Wispr Flow/Typeless comparisons and offline/developer guides. It also updates
the launch drafts, local Pages policy and handover, including the owner's stop on
all VM work. Desktop behavior and the published `12bc27f` app are unchanged.

- 19 content checks passed.
- Local Astro type/content/token checks and all 46 generated pages passed;
  44 indexable URLs and readable/social exports were verified.
- Two desktop Chromium checks passed: every public page's metadata/social image,
  and visible FAQ/application structured-data agreement. These are website checks,
  not native app acceptance.
- Locally generated output was pushed as a descendant to `gh-pages` at
  `f73dafb0f49a7065f943019643bf25f870a3875c`. Managed Pages publishing completed.
  No custom workflow was dispatched.
- Unauthenticated GETs returned HTTP 200 for home/download/changelog and all four
  changed guides/comparisons. All seven HTML bodies match the published Git tree
  exactly and the local build after Git LF normalization. Four font/CSS assets
  returned 200. See the live verification JSON and its retained producer.

Raw local logs/receipts are byte-pinned by `manifest.json`. Broader native Windows
and accuracy acceptance remain pending. The separate
[retention record](../../../../docs/BUILD_RETENTION.md) and cleanup verification
JSON confirm the owner's removal of 23.05 GiB across 85 targets. An independent
check found none remaining, verified the retained published ZIP checksum and
matched all 1,440 extracted payloads to their recorded hashes. Source, models,
profiles and audit evidence were preserved; no VM was created or booted.
