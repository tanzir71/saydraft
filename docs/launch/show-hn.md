# Show HN draft

Verified 14 November 2026. See the [shared facts and publication status](README.md).

## Title

Show HN: Saydraft – local voice dictation for Windows, open source

## Link

https://github.com/tanzir71/saydraft

## First comment

I'm the developer of Saydraft, a Windows tray app for local voice dictation.
Hold Ctrl+Win, speak and release. It recognizes speech with an installed
Parakeet or Whisper model, cleans the text and attempts delivery into the
original text field. History is written before that delivery attempt.

Rules cleanup works on its own. Optional AI cleanup uses pinned Qwen weights
through a local llama.cpp CPU or Vulkan runtime. Models are installed through
explicit setup actions with size/license disclosure and resumable downloads.
Speech and cleanup have no cloud fallback; audio retention and app update
checks default off.

The UI uses PySide6 and SQLite for local History and Notes. It includes vocabulary,
Snippets, per-app Style and a Scratchpad. Experimental Pro tools add Command
editing and spoken translation. The app code is MIT; dependencies and models
keep their own licenses.

You can try the source on Windows 10/11 x64 with Python 3.13 using the README.
There is no published installer release yet. Physical Windows acceptance,
signing and broader quality/performance qualification remain in progress;
the roadmap and retained measurements state what has actually been tested.

I'd appreciate feedback on setup and recovery behavior, particularly the cases
where a transcript is saved but cannot be delivered safely into the original
field.

## Posting reference

The [Show HN guidance](https://news.ycombinator.com/showhn.html) calls for a
project that people can try. The submission link above points to source and
installation instructions rather than a promotional landing page. The owner
posts and participates in the discussion.
