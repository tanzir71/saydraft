# Saydraft (formerly VoiceTray): Offline Wispr Flow / Typeless Parity Plan

> **What this is.** The single source of truth for Codex to take VoiceTray from "working offline dictation prototype" to **near-identical quality and UX to Wispr Flow and Typeless, with zero cloud dependence**. It also covers a website on GitHub Pages with the same aesthetic level as Wispr Flow's, SEO at every touchpoint, and the rename to **Saydraft**.
>
> **Supersedes:** `CODEX_HANDOFF.md` (milestones M0–M6, all done). Move it to `docs/history/CODEX_HANDOFF_v1.md` with `git mv` in P0.1. Don't delete it.
>
> **Researched:** 2026-11-11. Competitor facts carry a date and a source in §15. If something here contradicts what you see in the current code or at a source URL, stop and log it under `## Open Questions`. Don't guess.

---

## 0. Codex loop protocol (read first, every iteration)

1. Read `## 12. Loop State`. Pick the **first unchecked task** in the lowest incomplete milestone, unless it is blocked by an **OWNER GATE** (§0.2). If it is, skip to the next task that isn't gated and note the skip.
2. Work on a branch named `p<milestone>-<slug>` (for example `p3-parakeet-engine`). One task per PR where feasible. The owner reviews with Greptile and test builds, so keep PRs reviewable (under about 600 changed lines excluding generated files and fixtures).
3. Run verification before you check anything off:
   - `python -m pytest tests -q` (with `QT_QPA_PLATFORM=offscreen`)
   - `python -m saydraft.eval` (or `voicetray.eval` before P1). The pass rate must not drop.
   - the task's own **Acceptance** bullets
   - for site tasks: `npm run build && npm run test && npm run storybook:build` in `site/`
4. Check the task off, then append one line to `## 14. Changelog`: `YYYY-MM-DD | task | summary | files`.
5. If a task can't be done, add `BLOCKED: <reason + exact error>` under it and move on. Never skip silently.
6. Never violate §2 Hard Constraints. When in doubt, take the simpler, more reliable path and write down the trade-off in the PR.

### 0.1 Definition of "parity"

Parity means a user switching from Wispr Flow or Typeless on Windows finds no missing **daily** behaviour: same hotkey muscle memory, same "speak messy, get clean text in any app" result, a similar pill or bar, a hub with history, dictionary, snippets and styles, and a similar latency feel. The §1 scorecard is the contract. Anything that needs the cloud (team sync, web search in Ask, cross-device sync) is a declared non-goal (§13).

### 0.2 OWNER GATES (Codex must not cross these without a written "approved" from the owner in the PR or this file)

| Gate | Decision needed | Default if approved | Blocks |
|---|---|---|---|
| **G1 Name** | Adopt **Saydraft** (§5) and rename the GitHub repo | `tanzir71/voice_tray` → `tanzir71/saydraft` | P1.4, P9.6 |
| **G2 License** | The repo has **no LICENSE file** today. Choose MIT (recommended: same as Handy and FreeFlow) or GPL-3.0 | MIT | P0.3, all listings |
| **G3 Visual lock** | Approve §9 tokens or supply a Figma frame set (owner rule: lock taste in Figma before execution) | §9 tokens | P6.1 final visuals, P9.3+ final visuals (scaffolding may proceed) |
| **G4 History rewrite** | Purge `dist/` and `build/` (≈500 MB, 1,714 tracked files) from git history with `git filter-repo` | **No**. Untrack only | optional P0.2b |
| **G5 Code signing** | SignPath Foundation (free for OSS) or Azure Trusted Signing (paid) | SignPath | P8.3 |
| **G6 Domain** | Buy `saydraft.app` (available on 2026-11-11; `saydraft.com` is taken) or stay on `tanzir71.github.io/saydraft/` | github.io first | P9.5 canonical |
| **G7 Fine-tune spend** | Train a custom 0.8B cleanup LoRA on synthetic data (uses cloud LLM at **dev time only**) | not approved | P10 (Labs) |
| **G8 Site analytics** | None, or a cookieless self-host (for example GoatCounter) | none | P9.5 |
| **G9 Old site** | What happens to `voicetray-offline.vercel.app`: banner plus canonical to new site. **Never delete the Vercel project** | banner + canonical | P9.7 |
| **G10 Photography** | Source the motion-blur photos (own shoot, licensed stock, or licensed AI-generated) | gradient placeholders | P9.3 final |

**Owner approvals (2026-11-12, Codex chat):** G1 **approved** — adopt Saydraft and
the planned rename; G2 **approved** — MIT; G3 **approved** — use the §9 visual
tokens. Owner's exact response: "Approve Saydraft, MIT, and §9 visual tokens".
Other gates remain as listed above.

---

## 1. Parity scorecard (the contract)

Legend: **WF** = Wispr Flow, **TL** = Typeless. "Target" is what Saydraft must do offline on Windows 10/11 x64.

| # | Capability | WF / TL today | Saydraft target | Milestone |
|---|---|---|---|---|
| 1 | Push-to-talk default | WF: **Ctrl+Win** on Windows; Fn on Mac | Default **Ctrl+Win** (hold). Keep **F9** as an alternate for existing users | P5.1 |
| 2 | Hands-free | WF: Ctrl+Win+Space; finish with Ctrl+Win or the red stop on the bar | Same chord, plus double-tap of the PTT chord; Esc cancels | P5.5 |
| 3 | Cancel | Esc | Esc (passes through to the app as WF does); speech under 0.5 s is discarded | P5.5 |
| 4 | Paste last transcript | WF: Shift+Alt+Z | Shift+Alt+Z | P5.5 |
| 5 | Command Mode | WF: Ctrl+Win+Alt; select text and speak an instruction; Pro-only; behind "Experimental"; shows a copy popup where it can't write back | Same chord; local LLM; gated by hardware tier; same popup fallback | P7.1 |
| 6 | Scratchpad / View diff | WF: Win+Alt+S / Ctrl+Win+D | Same chords | P6.5 |
| 7 | Floating bar | WF "Flow Bar": bottom-center capsule, idle bubble, white bars that move with volume, start ping, no spinner (bars freeze, then text pastes) | "Saydraft Bar" with the same state model (§8.1), original sounds and visuals | P6.2 |
| 8 | Release → text latency | WF reviews: under ~2 s "in normal conditions"; short utterances feel near-instant | p50 ≤ **600 ms** / p95 ≤ **1.2 s** (≤ 20 s audio, rules only); with LLM p50 ≤ **1.2 s** / p95 ≤ **2.0 s** on the Pro tier | P3, P4 |
| 9 | Recognition accuracy | Cloud models | Parakeet TDT 0.6B v3 default (≈6.3% avg WER on Open ASR vs Whisper large-v3 ≈7.2%); English-max Parakeet v2 (≈6.0%) | P3.2 |
| 10 | Filler removal | Both | Rules (existing) + LLM | P4 |
| 11 | Backtrack / self-correction | WF "Backtrack": trigger words ("actually", "scratch that", "never mind") and natural restatement; must not trigger on "I actually agree…" | Rules (existing M3.1) + LLM + validator; adversarial tests | P4.5, P4.7 |
| 12 | Lists, new line/paragraph, spoken punctuation, em dash, ellipsis | Both | Full command set (§7.4) | P4.5 |
| 13 | Numbers, dates, currency, emails, URLs (ITN) | Both | Deterministic ITN + LLM; validator protects digits | P4.5 |
| 14 | Context-aware caps/spacing at caret | WF adjusts to cursor context; drops trailing period in messaging apps | UIA reads text before the caret; per-app-group trailing-period rule | P5.4 |
| 15 | Styles per app | WF: Formal / Casual / Very casual, desktop and English-first; 4 "Auto Cleanup" levels. TL: tone per app | App groups × tone × intensity (4 levels) | P5.7 |
| 16 | Personal dictionary | WF: manual add + **auto-learn from your corrections** (toggle). TL: auto + manual | Manual + auto-learn from post-paste edits via UI Automation + ASR biasing | P5.6, P3.5 |
| 17 | Snippets | WF: voice-triggered text expansion | Same, in the Hub | P6.3 |
| 18 | Languages | WF: 100+, auto-detect; picking 2–3 is recommended. TL: 100+, mixed-language speech | Parakeet v3 (25 European languages, auto LID) → Whisper large-v3-turbo for everything else (99 languages); pin up to 3; code-switching eval slices | P3.3–P3.4 |
| 19 | Translate while speaking | TL "Translate" | Local LLM translation, tier-gated, Labs | P7.2 |
| 20 | Ask about selected text | TL "Ask anything" (includes web) | Summarize, explain or rewrite the selection **locally**; no web | P7.3 |
| 21 | Whisper mode (quiet speech) | WF | Gain + AGC + denoise + lower VAD threshold | P7.4 |
| 22 | Code / IDE mode | WF: Cursor/Windsurf file tagging, camelCase/snake_case, CLI formatting | Code app group: identifier casing commands, `@file` tagging, no prose rewrites | P4.5 |
| 23 | "Press enter" | WF: sends Return after pasting | Opt-in trailing voice command | P4.5 |
| 24 | Hub | WF Hub: Home (shortcut, activity, stats), Dictionary, Snippets, Style, Settings | Same IA (§8.3) | P6.3 |
| 25 | History + raw vs clean | WF: Recent activity + View Diff. TL: on-device history | SQLite history, diff view, retry with another model (when audio kept) | P6.3 |
| 26 | Onboarding | WF: 8 steps including a **practice sandbox** (fake Gmail/Notion) | 6 steps with a sandbox, no account step | P6.4 |
| 27 | Notetaker (meetings) | WF Notetaker: Windows/Mac; speakers, summary, next steps; Zoom/Meet/Teams/Slack/in person | Local loopback + mic capture, diarization, local summary; Labs | P7.5 |
| 28 | Privacy | WF needs internet for transcription. TL: cloud with zero-retention claims | **No network at runtime**, provable (§2, P0.6, P8.6) | P0.6 |
| 29 | Price / limits | WF free: 2,000 words/week (Pro $15/mo or $12/mo annual). TL free reportedly cut to 2,000/week on 2026-09-22 (Pro $12/mo annual, $30 monthly) | Free, unlimited, open source | — |

---

## 2. Hard constraints (never violate)

1. **Offline at runtime.** No cloud STT or LLM, no telemetry, no crash upload. The only network use is (a) model and runtime downloads the user starts, from URLs pinned in `models/manifest.json` with SHA-256 verification, and (b) an optional update check that is **off by default**. A runtime `NetworkGuard` enforces this (P0.6). Loopback (`127.0.0.1`) to our own sidecar is allowed.
2. **Never lose the user's words.** Write raw and cleaned text to history **before** any insertion attempt. Every failure falls back to the less-processed text, never to nothing. Schema migrations **copy** data, never drop columns or rows, and keep a pre-migration backup file.
3. **No deletion of owner-owned things without explicit approval.** This covers user data dirs, model folders, git branches, tags, releases, the Vercel project, GitHub settings and untracked files. Removing dead code **via a git commit in a PR** is allowed: it is reversible and reviewed. Anything else goes to an `_archive/` folder plus a PR note.
4. **Insertion safety.** Never paste into a password field (UIA `IsPassword`). Always restore the previous clipboard **in all formats**. Never type into a window other than the one focused when recording started; if focus moved, leave the text in history and show a toast.
5. **Windows 10/11 x64 first.** Python 3.12+ (3.13 is fine). Keep platform-specific code behind interfaces so a macOS port isn't precluded.
6. **Licenses.** Models download on demand and each shows its license in Settings → Models and on the site's credits page. Never bundle a model whose license forbids redistribution. **CC-BY-4.0 models (Parakeet) require attribution.** Do not use or ship `superwhisper/s1-mini` by default (custom license); a user may point at it manually.
7. **Trademarks and assets.** Never use "Wispr", "Flow" or "Typeless" in the product name, repo name, icons or package IDs. Comparison pages may name competitors factually (nominative use), with a dated "not affiliated" note, **no competitor logos**, and no copied copy, images, sounds or illustrations. Aesthetic parity means the same *level* of craft and a similar design *language*, never cloned assets.
8. **Owner's visual rules** (stated preferences, apply to the app UI and the site): flat colours; **no drop shadows**; no heavy outlined boxes (hairlines at low alpha only); generous whitespace; more visuals, less text; art-directed layouts.
9. **Component library + Storybook are mandatory** for the website (owner's standing rule). The Qt app gets the equivalent: a live **component gallery** window with every widget state (P6.6).
10. **Latency budgets** (§1 row 8). Show cleanup that would blow the budget **as rules-only output in time**. The LLM call times out; it never blocks insertion.
11. **No console window** in normal use. Rotating logs in `%LOCALAPPDATA%\Saydraft\logs\` (5 × 1 MB). Logs never contain transcript text unless debug logging is explicitly on.
12. **Accessibility.** Every Hub control is keyboard-reachable with a screen-reader name. The bar never steals focus.

---

## 3. Current state audit (2026-11-11)

**Stack:** Python 3.13, PySide6 6.11.1, faster-whisper 1.2.1 (default `base` int8), webrtcvad, `keyboard` 0.13.5 (global hooks), pyperclip, SQLite history, PyInstaller one-folder build. Site: hand-written `index.html` + `demo/` on Vercel (`voicetray-offline.vercel.app`), dark purple theme. Tests: about 45 test files, eval corpus of 42 cases.

**Good (keep):** the cleanup architecture (rules → optional LLM → validator → fallback) in `voicetray/dictation/`; hold-to-talk and lock; history-before-insert; per-app profiles; the eval harness; crash guard; single instance; onboarding, settings and history windows in Qt.

**Gaps that block parity (fix in this plan):**

| ID | Gap | Evidence | Fix |
|---|---|---|---|
| G-1 | **Recognition quality.** Whisper `base` is far below cloud quality and below Parakeet/Qwen3-ASR | `config.py` `stt.model_size="base"` | P3 |
| G-2 | **LLM cleanup doesn't ship.** `llama-cpp-python` isn't in `requirements.txt`; LLM off by default; JSON output format adds tokens and parse failures | `requirements.txt`, `llm_local.py` | P4 |
| G-3 | **God object still drives runtime.** `voicetray/legacy_app.py` (1,006 lines) is the worker core behind `LegacyWorkerController` | `app.py:41` | P2 |
| G-4 | **Hotkeys via `keyboard`** (unmaintained). Default F9 instead of Ctrl+Win. No mouse buttons. Start-menu flash on Win chords | `hotkeys.py` | P5.1 |
| G-5 | **Clipboard restore is text-only** (pyperclip). Images and rich formats are lost. Dictations pollute Win+V history | `insert/inserter.py` | P5.2 |
| G-6 | **App detection by window title only**; no process name, no caret context, no password detection | `legacy_app.py:513–560` | P5.3 |
| G-7 | No auto-learn dictionary, no paste-last, no scratchpad, no diff view, no styles matrix, no command mode | — | P5–P7 |
| G-8 | Separate Settings and History dialogs instead of a Hub; pill shows a spinner (WF has none) | `ui/` | P6 |
| G-9 | **Repo hygiene:** `dist/` + `build/` are **tracked** (1,714 files; `dist/` ≈ 441 MB; `.git` ≈ 205 MB); `.gitignore` only ignores `.vercel`; `__pycache__` tracked; **no LICENSE**; no CI | `git ls-files` | P0 |
| G-10 | Packaged build pulls in unrelated packages (`pyarrow`, `aiohttp`, `cryptography`, `hf_xet`), so it was built in a dirty environment | `dist/VoiceTray/_internal/` | P8.1 |
| G-11 | Website is a dark generic landing page on Vercel with no SEO architecture (one page, no comparison pages, no structured data) | `index.html` | P9 |
| G-12 | Naming: "VoiceTray" describes the plumbing (a tray icon), not the outcome, and both words are generic, so the search results can't be owned | — | P1 |

**Note:** Codex's earlier `WISPR_OFFLINE_PARITY_PLAN.md` was **not found** in the repo or its git history on 2026-11-11. This file replaces it under the same name.

---

## 4. Competitor teardown (what we're matching, as of Nov 2026)

### 4.1 Wispr Flow (cloud; Mac, Windows, iOS, Android)
- **Positioning:** "Don't type, just speak." Speech turns into polished writing in every app. Claims 4× faster than typing (45 vs 220 wpm). Now also sells **Notetaker** (meetings) in the same app.
- **Flow Bar:** bottom-center capsule; idle bubble (hideable); listening shows white volume bars and a start ping; on release the bars freeze and the cleaned text pastes. **No spinner, no live text in the field.** Click the bar to start hands-free.
- **Hub:** Home (welcome, shortcut, activity, stats), Dictionary, Snippets, Style, Settings. Keyboard navigation documented.
- **Windows shortcuts:** PTT Ctrl+Win · Hands-free Ctrl+Win+Space · Command Ctrl+Win+Alt · Paste last Shift+Alt+Z · Transform Ctrl+Win+P · View diff Ctrl+Win+D · Scratchpad Win+Alt+S · Cancel Esc. Rules: at most 3 keys, needs a modifier or a mouse button; Ctrl+Win suppresses Start/Search while held.
- **Smart Formatting & Backtrack:** trigger words ("actually", "scratch that", "never mind") or natural restatement ("as a gift… as a present"). Has a documented way to say "actually" without triggering.
- **Styles:** Formal, Casual, Very casual per context; Auto Cleanup with 4 intensity levels; trailing periods dropped in messaging apps.
- **Dictionary:** auto-learns corrected spellings (toggle) plus manual add; team sharing.
- **Command Mode:** select text, hold the chord, speak ("make this more concise", "translate to Polish"). Sends the textbox contents and the selection. Pro-only, under Settings → Experimental. Shows a copy popup where it can't write back (for example Google Docs).
- **Privacy:** "An internet connection is required for transcription." SOC 2 Type II / ISO 27001 / HIPAA claims; Privacy Mode; zero-retention agreements with LLM vendors.
- **Pricing:** free 2,000 words/week on desktop; Pro $15/mo or $12/mo annual.

### 4.2 Typeless (cloud; macOS, Windows, Linux, iOS, Android)
- **Dictate:** removes fillers and repetition, resolves mid-sentence corrections ("keeps the final intent"), auto-formats lists, steps and key points; personal style learning; personal dictionary (auto + manual); 100+ languages with **mixed-language speech**; tone per app.
- **Translate:** speak in one language, get natural phrasing in another.
- **Ask anything:** speak to edit selected text (shorten, lengthen, change tone); ask about selected or read-only text (summarize, explain, translate); quick web answers and actions.
- **Privacy:** zero cloud retention, on-device history, not used for training.
- **Pricing:** Pro $12/mo annual or $30 monthly; free tier reportedly cut from 8,000 to 2,000 words/week on 2026-09-22.

### 4.3 Open-source and local landscape (our real competition for "free + offline")

| Project | Stack | Local? | Cleanup | Windows | Notes |
|---|---|---|---|---|---|
| **Handy** (cjpais) | Tauri (Rust + React) | Yes: Whisper, Parakeet v3, Silero VAD | Minimal / none | Yes, `winget install cjpais.Handy` | ≈31.6k stars; MIT; "most forkable", deliberately simple |
| **OpenWhispr** | Electron + whisper.cpp + sherpa-onnx | Yes (also cloud) | AI agents and cloud cleanup; local streaming preview via **Nemotron** on CPU | Yes | Closest feature competitor; runs sherpa-onnx as a separate WebSocket process for crash isolation |
| **FreeFlow** (zachlatta) | Native macOS | **Cloud by default** (Groq); local via an OpenAI-compatible server | LLM post-processing, Edit Mode, context awareness | No | ≈3.0k stars; MIT |
| **VoiceInk** | macOS | Yes | Yes | No | GPL-3.0 |
| **Superwhisper** | Proprietary | Yes (paid) | Yes | Yes (Win 10/11) | Paid |

**Our wedge:** the only **Windows-first, fully offline** app with **Wispr-grade cleanup** (backtrack, styles, auto-learn dictionary, command mode) and **Wispr-compatible shortcuts**, with offline behaviour you can verify (NetworkGuard, firewall option, open source).

---

## 5. Name and rename

### 5.1 Recommendation: **Saydraft**

- **Meaning:** *say* it, get a *draft*: the outcome, not the plumbing. Tagline: **"Speak messy. Paste polished."**
- **Availability (checked 2026-11-11):** **0** GitHub repos named `saydraft`; no product or trademark hits in web search; `saydraft.app`, `saydraft.dev`, `saydraft.org` and `getsaydraft.com` unregistered (`saydraft.com` is registered).
- **SEO:** a unique token lets the brand own its results page quickly. Keyword intent ("offline dictation", "Wispr Flow alternative") goes into descriptors, not the name (§10).
- **Rejected after checks:** *Sotto* (an existing macOS dictation app), *Hushkey*, *Sayso*, *Plainsay*, *Saywrite*, *Dictare*, *OpenDictate*, *HushWrite* (existing dictation repos or apps), *Kotha* (an existing Bangladeshi app), *Bolo* (Google used it). Anything with "Flow" or "Wispr" is out on trademark grounds.
- **Alternate if the owner prefers a personal-story name:** **Kontho** (Bangla for "voice"). No dictation repos use it and `kontho.dev` is free, but search results are dominated by a 2019 film, so SEO is weaker.

### 5.2 Rename runbook (P1; **G1** must be approved first)

Order matters. Each step is its own commit.
1. **Code:** rename package `voicetray/` → `saydraft/` (`git mv`). Keep a thin `voicetray/__init__.py` shim that re-exports from `saydraft` and logs a deprecation warning for one release. Rename `VoiceTray.spec` → `Saydraft.spec`, the exe → `Saydraft.exe`, and the AppUserModelID → `Tanzir.Saydraft`.
2. **User data migration (copy, never move):** on first run, if `%LOCALAPPDATA%\VoiceTray\` exists and `%LOCALAPPDATA%\Saydraft\` doesn't, **copy** config, history.db (+ WAL), glossary, snippets, logs and models into the new dir. Write `MIGRATED_FROM_VOICETRAY.txt` and leave the old dir untouched. Tests cover a partial previous copy (idempotent resume).
3. **Autostart:** if the HKCU `Run` value `VoiceTray` exists, write a `Saydraft` value and then remove **only** the `VoiceTray` value that the app itself created (it's app-managed state; log it). Single-instance mutex: new name, plus a check for an old VoiceTray instance with a toast "Close VoiceTray to avoid double hotkeys".
4. **Strings and assets:** tray tooltip, window titles, About, icons, onboarding copy, README, `llms.txt`, `docs/`.
5. **GitHub (owner runs it, or Codex with explicit approval):** `gh repo rename saydraft -R tanzir71/voice_tray`, then `git remote set-url origin https://github.com/tanzir71/saydraft.git`. GitHub redirects old repo URLs and git remotes **as long as no new repo takes the old name**. Do not create a new `voice_tray` repo.
6. **Pages and old site:** the Pages URL becomes `https://tanzir71.github.io/saydraft/` (github.io paths **don't** redirect after a rename). For the old Vercel site, see **G9**: banner + `<link rel="canonical">` to the new home. Don't delete it.
7. **Local folder** `C:\Users\tanzir\Desktop\voice_tray`: the owner renames it (optional) after closing the editor and Codex.

---

## 6. Target architecture

### 6.1 ADR-001: stay on Python + PySide6 (decided; don't re-litigate)

The app already works on this stack, and the parity gaps are about models, Windows integration and UX, not the language. Handy (Tauri) and OpenWhispr (Electron) show either path can win. A rewrite would burn months for no user-visible gain. **Revisit only if**, after P4, p95 latency or idle RAM misses §1/§6.4 on the reference machine **because of** Python overhead (profile it first).

### 6.2 Process model

```
Saydraft.exe  (PySide6, main thread = Qt UI only)
 ├─ HotkeyThread      : WH_KEYBOARD_LL + WH_MOUSE_LL hooks, own GetMessage loop      → signals
 ├─ AudioThread       : WASAPI capture (sounddevice), 16 kHz mono ring buffer, RMS
 ├─ SessionWorker     : state machine; runs VAD → ASR → rules → (LLM) → format → insert
 │    ├─ ASR in-process via sherpa-onnx / onnxruntime / faster-whisper (thread pool, 1 job)
 │    └─ LLM via HTTP to 127.0.0.1 sidecar (timeout-bounded)
 ├─ ContextService    : foreground process/exe, app group, UIA focused element (caret text, selection, IsPassword)
 └─ LearnService      : post-paste edit watcher → dictionary suggestions
llama-server.exe (sidecar, optional; started on demand; 127.0.0.1 only, random port, random API key; idle-unload)
```

Why a sidecar for the LLM: it isolates crashes (a native OOM can't kill dictation), lets us ship llama.cpp's prebuilt **Vulkan** (NVIDIA, AMD and Intel GPUs) and CPU builds without compiling `llama-cpp-python`, and avoids GIL contention. OpenWhispr isolates its sherpa-onnx streaming server for the same reason.

### 6.3 Package layout (after P1/P2)

```
saydraft/
  __main__.py, main.py, app.py                 # entry, single instance, Qt shell
  core/        session.py (state machine), events.py, container.py (DI), timings.py
  audio/       capture.py, ring.py, vad_silero.py, vad_webrtc.py (fallback), enhance.py (whisper mode)
  asr/         base.py (AsrEngine, StreamingAsrEngine), sherpa_parakeet.py, sherpa_stream.py,
               whisper_ct2.py, qwen3_onnx.py (labs), router.py, biasing.py
  cleanup/     rules/ (moved from dictation/), itn.py, commands.py, code_mode.py,
               llm/ (sidecar.py, client.py, prompts/, validate.py), styles.py, formatter.py (caret-aware)
  context/     foreground.py, uia.py, app_groups.py, browser_sites.py
  insert/      clipboard_win.py (all-format snapshot), sendinput.py, inserter.py, uipi.py
  hotkeys/     llhook.py, chords.py, startmenu_mask.py
  learn/       edit_watcher.py, align.py, suggest.py
  features/    command_mode.py, translate.py, ask.py, scratchpad.py, notes/ (notetaker)
  data/        db.py (migrations), history.py, dictionary.py, snippets.py, styles_store.py, stats.py
  models/      manifest.json, manifest.py, downloader.py (sha256, resume), hardware.py (probe + bench → tier)
  privacy/     netguard.py, firewall.py
  ui/          bar.py, hub/ (home, history, dictionary, snippets, style, notes, settings), onboarding/,
               scratchpad.py, toast.py, theme/ (tokens → QSS), gallery.py, sounds/
  eval/        __main__.py, asr_wer.py, cleanup.py, latency.py, adversarial.py
```

### 6.4 Resource budgets (reference: a mid-range 2023+ laptop, 16 GB RAM, no dGPU)

| Metric | Budget |
|---|---|
| Launch → tray ready | ≤ 2.0 s (models warm in the background afterwards) |
| Idle RAM, models unloaded | ≤ 180 MB |
| Warm RAM, Parakeet loaded | ≤ 1.3 GB |
| LLM sidecar RAM (0.8B Q4) | ≤ 1.2 GB; unload after 15 min idle (configurable) |
| Installer size without models | ≤ 250 MB |
| CPU while idle | ≈ 0% (no polling loops; hooks and events only) |

---

## 7. Engine plan

### 7.1 Speech recognition: model matrix and router

| Role | Model | Why | Runtime | License | Download |
|---|---|---|---|---|---|
| **Default** (English + 25 European languages, auto language ID) | **NVIDIA Parakeet TDT 0.6B v3**, int8 | ≈6.3% avg WER on the Open ASR Leaderboard vs Whisper large-v3 ≈7.2%; CPU-only real time; RTFx ≈36 on a desktop CPU via onnx-asr | **sherpa-onnx** (pip wheels for Windows; offline transducer + TDT; Silero VAD in the same package) | CC-BY-4.0, attribution required | ≈0.5 GB |
| **English-max** | Parakeet TDT 0.6B **v2**, int8 | Slightly better English WER (≈6.0%) | sherpa-onnx | CC-BY-4.0 | ≈0.5 GB |
| **All languages** (Arabic, Bengali, Hindi, CJK, …) | **Whisper large-v3-turbo** via faster-whisper int8 | 99 languages; existing engine code | CTranslate2 | MIT | ≈0.8 GB |
| **Low-end fallback** | Whisper base / small (existing) | Old CPUs | CTranslate2 | MIT | 0.15–0.5 GB |
| **Live preview** (Labs) | **Nemotron Speech Streaming EN 0.6B** / **Nemotron 3.5 ASR Streaming 0.6B** (40 language-locales), int8 | Cache-aware streaming with partial results on CPU (OpenWhispr ships this) | sherpa-onnx `OnlineRecognizer` (OpenWhispr notes Nemotron needs **sherpa-onnx ≥ 1.13.4** or it silently mis-decodes) | EN model: NVIDIA Open Model License (per the HF card); 3.5 multilingual: a conversion card cites OpenMDW-1.1. **Verify both on the upstream cards**, show the license, download on demand only | ≈0.65 GB |
| **Evaluate** (Labs) | **Qwen3-ASR-0.6B** | ≈6.4% avg WER; 30 languages including Arabic and Hindi; language ID | ONNX CPU export (≈2.5 GB) or a native port; spike only | Apache-2.0 | 1.3–2.5 GB |
| VAD | **Silero VAD** | Better than webrtcvad for trimming and long-form chunking | sherpa-onnx | MIT | 2 MB |

**Router rules (`asr/router.py`):**
1. The user picks **Auto** or pins up to 3 languages (WF also recommends 2–3).
2. If every pinned language is in Parakeet v3's set, use Parakeet v3; if the only pin is English and "English-max" is on, use v2.
3. Otherwise use Whisper large-v3-turbo with `language=` set when exactly one non-Parakeet language is pinned.
4. In Auto mode, run Parakeet first. If Parakeet's language ID is outside its set **or** confidence is low (empty or very short output for long audio, or a high ratio of non-Latin hallucinations), re-run on Whisper turbo **only if** the time budget allows; otherwise insert what we have and offer "Retry with All-languages model" in History.
5. Per-app override: an app group can force a model.

**Long dictation:** Silero VAD segments at pauses (max segment 25 s for Parakeet). Transcribe segments **while the user is still speaking** (background queue), so at release only the tail segment is left. This is the main latency lever. Soft cap 20 min (cloud competitors reportedly cap sessions around 6 min; verify before claiming it on the site).

**Dictionary biasing (P3.5 spike, report before building):** (a) sherpa-onnx **hotwords** with modified beam search: verify it works with NeMo TDT transducers in the pinned version and measure the WER gain on dictionary terms; (b) faster-whisper `initial_prompt`/`hotwords`; (c) always: post-ASR **phonetic + edit-distance correction** against dictionary terms (Double Metaphone + Damerau-Levenshtein, word-boundary aware, protected terms never altered).

### 7.2 Hardware tiers (set by onboarding benchmark, changeable in Settings)

`models/hardware.py` probes CPU (cores, AVX2/AVX-512), RAM, GPUs (DXGI adapter list; Vulkan-capable; VRAM), then times a bundled 8 s fixture through ASR and a 60-token LLM generation.

| Tier | Requirement (measured, not guessed) | ASR | Cleanup | Power features |
|---|---|---|---|---|
| **Lite** | ASR on the 8 s fixture > 1.2 s, or RAM < 8 GB | Whisper small/base | Rules only | — |
| **Standard** | ASR ≤ 1.2 s; LLM 0.8B ≥ 25 tok/s | Parakeet v3 | Rules + **0.8B** LLM when the need-score is high | Styles, auto-learn |
| **Pro** | GPU (Vulkan/CUDA) or LLM 2B ≥ 40 tok/s | Parakeet v3 (+ live preview) | Rules + **2B–4B** LLM | Command Mode, Translate, Ask, Notetaker summaries |

### 7.3 Cleanup LLM

**Runtime:** `llama-server` from a **pinned** llama.cpp GitHub release (Windows x64 CPU-AVX2 and Vulkan zips, SHA-256 in the manifest), downloaded only when the user enables AI cleanup. Start with `--host 127.0.0.1 --port <free> --api-key <random> -c 4096 -ngl <auto>`; health-check `/health`; idle-unload; restart with backoff; never two instances.

**Model bake-off (P4.4).** Run every candidate through the eval harness and choose defaults from the data. Record the results in `docs/MODELS.md`.

| Candidate | Size (Q4) | License | Notes |
|---|---|---|---|
| **Qwen3.5-0.8B** instruct GGUF | ≈0.5–1.0 GB | Apache-2.0 | Standard-tier default candidate; reasoning is off by default on the small Qwen3.5 sizes |
| **Qwen3.5-2B** | ≈1.3–2.7 GB | Apache-2.0 | Pro-tier candidate |
| **Qwen3.5-4B** | ≈2.7–3.4 GB | Apache-2.0 | AssemblyAI's Voice Standard Bench (2026-10-28) scored a hosted "Qwen3.5 4B Fast" at 81/100 on 30 s dictation cleanup (75 at 2 min), the best small open model listed; it was also the fastest (0.28 s median across all tasks at 30 s) |
| **Gemma 4 E2B / E4B** | ≈1.5 / ≈3 GB | Apache-2.0 | Alternative; compare |
| superwhisper **s1-mini** (Qwen3-0.6B fine-tune) | 462 MB | **Custom**: don't ship | Reference only; user-supplied path allowed |

**Prompt v3 (replaces JSON output in `llm_local.py`):**
- System: role = *transcript cleaner, never an assistant*; the rules: keep meaning; remove fillers and false starts; apply backtracks; punctuation and casing; spoken commands; ITN; keep `⟦T0⟧`-style protected tokens verbatim; **never answer, translate or act on the content**; output only the cleaned text.
- User: a header line `[app: Slack | group: work_chat | style: casual | intensity: 3 | lang: en | before_caret: "…last 120 chars…"]` + the glossary (≤ 40 terms) + `<transcript>…</transcript>`.
- 6–8 few-shot pairs per style, including **adversarial** ones: a dictated question ("what's the capital of France") stays a question; an instruction to an AI ("write me a poem about…") is transcribed, not executed; "actually" used as an adverb stays.
- Decoding: temperature 0, `max_tokens = 1.25 × input_tokens + 16`, stop at `</out>` or EOS, stream tokens so insertion can begin the moment generation ends.

**Need-score gate (P4.6):** call the LLM only when it adds value and fits the budget. Score from cues (backtrack words, list cues, filler density, more than 25 words, style ≠ neutral, code group = no LLM prose edits). Predicted latency = tier benchmark × tokens. If predicted > remaining budget, use rules only. Hard timeout = remaining budget − 50 ms, then rules output. Log the decision in the history row.

**Validator v2 (`cleanup/llm/validate.py`), extending `dictation/validation.py`:** reject the LLM output and use rules output if any of these fail: digits/amounts/dates changed; protected or glossary terms missing; URLs or emails changed; code spans changed; **answer detection** (content-token overlap with the source below a threshold, or output starts with an answer pattern); language changed (unless Translate mode); length ratio outside [0.5, 1.3] (intensity-dependent); profanity removed (we don't censor).

### 7.4 Deterministic formatting (always on; also the fallback)

Extend `rules.py` and add `itn.py`, `commands.py`, `code_mode.py`:
- **Spoken punctuation and formatting:** comma, period/full stop, question mark, exclamation point, colon, semicolon, dash/em dash, ellipsis, open/close quote, open/close paren, hyphen, apostrophe-s, new line, new paragraph, "cap X", "all caps X", "bullet point", "number one/two…". This is the command set AssemblyAI's bench checks.
- **ITN:** cardinals/ordinals (style-dependent: "two" stays a word in prose under 10, unless intensity ≥ 3), times ("three thirty pm" → 3:30 PM), dates, currency, percentages, phone numbers, emails ("john at example dot com"), URLs, versions ("v two point one").
- **Backtrack** (existing M3.1, extend): "actually", "scratch that", "never mind", "no wait", "I mean", "sorry", restatement detection ("as a gift… as a present"), and guards ("I actually agree", "no, wait for me").
- **Lists:** "first… second… third", "one… two…", "bullet point …"; numbered vs bulleted by app group.
- **Messaging rule:** a single-sentence message in the Messages or Work-chat groups drops its final period (WF behaviour); configurable.
- **"Press enter"** at the end → strip it and send Enter after paste (opt-in; never in the Email or Docs groups).
- **Code mode** (Code group: VS Code, Cursor, Windsurf, Windows Terminal, Claude Code/Codex CLI in terminal titles, JetBrains): "camel case foo bar" → `fooBar`; snake, kebab, pascal, constant case; "at file app dot py" → `@app.py`; "dot", "slash", "dash dash" in command context; no prose rewriting or final period; spoken symbols ("open paren").

### 7.5 Models manifest (`models/manifest.json`)

Each entry has `id`, `role`, `display_name`, `version`, `files[] {url, sha256, size}`, `license {spdx|name, url, attribution}`, `languages[]`, `min_tier`, `runtime`, `ram_mb`, `disk_mb`. Downloads are resumable (HTTP Range) into `%LOCALAPPDATA%\Saydraft\models\<id>\<version>\` via a temp dir, then an atomic rename after the SHA-256 check. **Never auto-delete old versions.** Settings → Models shows the disk used, with a manual "Remove…" that confirms first.

---

## 8. App UX spec

### 8.1 Saydraft Bar (replaces `ui/pill.py` visuals; keep the class contract)

| State | Visual | Sound | Notes |
|---|---|---|---|
| **Idle** (optional, on by default) | 36×8 px flat ink capsule, 24 px above the taskbar, bottom-center of the monitor with the focused window; 60% opacity | — | Hover: grows to 160×32 with the hint "Hold Ctrl+Win to dictate" (shows the configured chord). Click: starts hands-free. Settings: Show/Hide. |
| **Listening** | 164×36 capsule, flat `--bar-bg`; 14 vertical bars (2 px wide, 3 px gap, rounded) whose heights follow RMS with attack 30 ms / release 120 ms; a red dot appears only in hands-free mode (stop button) | Short original "tick" on start, ≤ 120 ms, −18 LUFS | Appears within 50 ms of the key going down. Speech under 0.5 s → discard and collapse. |
| **Live preview** (Labs, opt-in) | A one-line text strip **above** the bar showing partial text (last 60 chars), fading at the left | — | Never typed into the target app before release (WF doesn't either). |
| **Finalizing / Cleaning** | Bars freeze at their last heights, then a slow left-to-right **opacity shimmer** (no spinner) | — | If it takes over 1.5 s, show a 2-word label ("Cleaning up") at 80% opacity. |
| **Inserted** | Collapse to idle (no animation on the text) | Optional soft end tick (off by default) | The pasted text is the confirmation. |
| **Not inserted** (focus changed, password field, elevated window) | Bar turns `--bar-warn` for 2.5 s with a short reason + "Saved, press Shift+Alt+Z to paste" | — | The text is in history and the clipboard is restored. |
| **Error** (mic missing, model missing) | `--bar-error` + reason + a click target that opens the fix (Settings → Microphone / Models) | — | Never a modal dialog. |
| **Command Mode** | Capsule with a "⌘ Command" label to the left of the bars | Distinct tick | — |

Rules: frameless, `WindowDoesNotAcceptFocus`, `Tool`, top-most, **click-through except the stop/expand targets**, DPI-aware per monitor, no drop shadow, 1 px hairline at 8% alpha max.

### 8.2 Shortcuts (defaults; all rebindable; conflict detection)

| Action | Default | Alt |
|---|---|---|
| Push-to-talk (hold) | **Ctrl+Win** | F9 (legacy), mouse XButton1 |
| Hands-free toggle | **Ctrl+Win+Space**, or double-tap PTT | — |
| Command Mode (hold) | **Ctrl+Win+Alt** | — |
| Paste last | **Shift+Alt+Z** | — |
| Scratchpad | **Win+Alt+S** | — |
| View diff of last | **Ctrl+Win+D** | — |
| Cancel | **Esc** (passes through) | — |
| History-only capture (legacy F10) | F10 | — |

Implementation notes for P5.1: low-level hooks on a dedicated thread with its own message pump. Chords made only of modifiers fire on the *full chord down*. When a Win chord is used, inject a mask key (`vkE8`, the AutoHotkey "MenuMaskKey" technique) before Win-up so the Start menu doesn't open. Suppress chord keys only while a chord is active. Detect Wispr Flow running (`Wispr Flow.exe`) and warn about a chord clash. Low-level hooks don't receive input while an **elevated** window is focused unless Saydraft is elevated too: surface "Can't hear hotkeys in admin windows" with a docs link, and never auto-elevate.

### 8.3 Hub (one window replacing the separate Settings and History dialogs)

Left rail (icons + labels): **Home · History · Dictionary · Snippets · Style · Notes · Settings**. Window 1080×720 min 880×600; light/dark follows Windows; visual tokens from §9.2 (serif display headings, flat paper/ink, no shadows).
- **Home:** greeting; configured shortcut "keycaps"; this week's words, average WPM (words ÷ speaking seconds), time saved vs 40 wpm typing; last 5 dictations; model/tier chip; "Offline ✓" chip that opens Privacy.
- **History:** searchable reverse-chronological list (app icon, app name, time, cleaned text). Selecting a row shows the cleaned text, with a **Raw ↔ Clean** toggle and an inline **diff** (insertions in accent, deletions struck). Actions: Copy · Paste again · Retry (other model or LLM on/off; only if audio retained) · Add word to dictionary · Export (MD/CSV). The per-row "why" panel shows timings, models and the LLM decision.
- **Dictionary:** list with source chips (Manual / Learned / Imported), "Auto-add to dictionary" toggle (WF parity), replacement pairs ("sea sharp" → "C#"), protected terms, import/export.
- **Snippets:** trigger phrase → expansion, variables `{date}` `{clipboard}`; test field.
- **Style:** a matrix of app groups (Messages, Work chat, Email, Docs & notes, Code, AI chat, Other) × **tone** (Formal / Casual / Very casual) × **cleanup intensity** (1 Verbatim-ish · 2 Light · 3 Balanced · 4 Polished), with live before/after previews and per-app overrides (exe or site).
- **Notes:** the Scratchpad history and Notetaker notes (P7.5).
- **Settings:** General (start with Windows, bar visibility, sounds) · Shortcuts · Microphone (device, test meter, whisper mode) · Languages · Models (tier, downloads, licenses, disk) · AI cleanup (on/off, model, max latency) · Privacy (network status, firewall rule, audio retention: **off** by default / keep N days / keep forever, telemetry: none) · Advanced/Labs (live preview, Command Mode, Translate, Ask, Notetaker) · About (version, licenses, credits).

### 8.4 Onboarding (replaces `ui/onboarding.py` flow; no account step)

1. **Welcome:** one sentence + "Your voice never leaves this PC."
2. **Microphone:** device picker + live bar meter + "Say 'testing one two three'". Windows mic privacy check with a deep link to `ms-settings:privacy-microphone`.
3. **Set up models:** hardware benchmark (≈10 s) → recommended tier → one-click download with per-file progress, pause/resume, SHA-256 check. Show sizes and licenses.
4. **Shortcut:** press-to-learn; Wispr-compatible preset preselected; conflict check.
5. **Try it (sandbox):** a fake chat box and a fake email box **inside the window**; prompts to say something messy with a backtrack and a list; shows a before/after with edit chips. Teach by doing, as WF's sandbox does.
6. **Style quick pick:** casual vs formal for Messages/Email → land on Hub Home.

### 8.5 Dictionary auto-learn (P5.6)

After each insertion, remember `{hwnd, UIA element RuntimeId, inserted text, caret range, timestamp}`. When focus leaves that element, or 15 s pass, read its text (ValuePattern/TextPattern; skip passwords and unreadable controls). Word-align the inserted span against the current span. A **single-token substitution** where the new token isn't in a frequency wordlist (or is a capitalization change of a proper noun) and is phonetically or edit-distance close becomes a suggestion. If "Auto-add" is on, add it and show a toast with **Undo**. Never upload; never read other fields.

### 8.6 Notetaker (P7.5, Labs)

Capture mic + **WASAPI loopback** (spike: `sounddevice` WASAPI loopback support vs `PyAudioWPatch` vs `soundcard`; pick the one that works with the pinned PortAudio). Chunked Parakeet ASR with VAD. Speaker diarization via sherpa-onnx (pyannote segmentation + speaker embedding models; verify licenses). Local summary (Pro tier LLM): title, summary by topic, decisions, next steps with owners. Saves Markdown to Notes. **Consent UX:** a persistent "Recording meeting" capsule state; never auto-starts; never joins calls as a bot. If the owner's other desktop-audio project already has working loopback capture, port it rather than re-inventing.

---

## 9. Website: GitHub Pages, at Wispr Flow's level of craft

### 9.1 What makes the reference site work (observed 2026-11-11), and how we translate it

| Observed on wisprflow.ai | Why it works | Saydraft translation (original, not copied) |
|---|---|---|
| Warm cream paper background (`#FFFFEB`), near-black ink (`#1A1A1A`) | Calm, editorial, "paper" metaphor for writing | Our own warm oat paper `#F5F2E9` + ink `#141414` |
| Display serif (**EB Garamond** 400) at 96–120 px with **italic emphasis words** ("Don't type, *just speak.*"); geometric sans body (**Figtree**) | Literary voice, human and confident | **Instrument Serif** (display, italic emphasis) + **Geist** body + **Geist Mono** labels (all SIL OFL; verify at install). Different faces, same register |
| Full-bleed colour **sheets** with large top radii that stack as you scroll (near-black, deep green `#034F46`, sand `#E4E4D0`) | Rhythm and chapters without drawing boxes | Sheets in `--night #111111`, **midnight indigo** `--deep #1C2740`, sand `--paper-raised #ECE7DA` |
| Floating pill nav with a Dictation/Notetaker toggle; CTA filled lavender **with a black outline** | Product feel | Floating pill nav; CTA **flat ink fill, no outline** (owner rule: no strong strokes) |
| Hero: messy speech flowing as **text on a curved path** into the product's bar, with green "edit chips" ("Added question mark") | Shows the product's magic without a video | **Ribbon**: messy transcript runs along an SVG path into a live **Saydraft Bar** replica; clean text emerges after it; edit chips in our palette ("Backtrack: 2 → 3", "Removed 'um'", "Made a list") |
| Motion-blurred lifestyle photography with the bar floating over it | Speed and humanity | Same *art direction* using **our own** photos (G10) or flat gradient fallbacks |
| Scroll-highlighted feature rows (inactive rows fade) | Focus | Same pattern with our features |
| Privacy card with circular certification badges | Trust | Verifiable facts instead of certificates: "0 network calls while dictating", "Open source (MIT)", "Works with Wi-Fi off", with a link to "Verify it yourself" |
| Logo wall ("Used by professionals at") | Social proof | **Don't fake it.** Use a "Built on open models" credits band (text wordmarks: NVIDIA Parakeet, Whisper, Qwen, llama.cpp, sherpa-onnx) + a live GitHub star count (fetched at build) |

### 9.2 Design tokens (`design/tokens.json`, shared by the site **and** the Qt theme; G3 approves)

```json
{
  "color": {
    "paper": "#F5F2E9", "paperRaised": "#ECE7DA", "ink": "#141414", "inkMuted": "#5B5A55",
    "night": "#111111", "deep": "#1C2740", "onDark": "#F5F2E9", "onDarkMuted": "#B9B6AC",
    "signal": "#FF5B3A", "mist": "#DDE6F6", "hairline": "rgba(20,20,20,0.08)",
    "barBg": "#141414", "barFg": "#F5F2E9", "barWarn": "#B45309", "barError": "#B42318"
  },
  "font": {
    "display": "'Instrument Serif', 'Iowan Old Style', Georgia, serif",
    "body": "'Geist', 'Segoe UI', system-ui, sans-serif",
    "mono": "'Geist Mono', 'Cascadia Code', ui-monospace, monospace"
  },
  "type": {
    "displayXL": "clamp(56px, 9vw, 128px)/0.95 -0.035em",
    "displayL": "clamp(44px, 6.5vw, 96px)/0.98 -0.03em",
    "displayM": "clamp(34px, 4.5vw, 64px)/1.02 -0.025em",
    "h3": "clamp(26px, 2.6vw, 40px)/1.1 -0.015em",
    "bodyL": "19px/1.5 0", "body": "16px/1.55 0", "eyebrow": "12px/1.2 0.14em uppercase mono"
  },
  "radius": { "sheet": "clamp(28px, 5vw, 64px)", "card": "20px", "pill": "999px", "chip": "999px" },
  "space": { "section": "clamp(96px, 12vw, 168px)", "gutter": "clamp(20px, 5vw, 64px)", "max": "1200px" },
  "motion": { "ease": "cubic-bezier(.2,.7,.2,1)", "fast": "160ms", "base": "320ms", "slow": "700ms" },
  "elevation": "none (flat; no shadows anywhere)"
}
```

### 9.3 Stack and repo layout

- **Astro** (latest stable, static output) renders **React TSX components** to static HTML at build time. Hydrate only the interactive islands (`Ribbon`, `BarDemo`, `StyleSwitcher`). FAQ uses native `<details>`.
- **Storybook** (`@storybook/react-vite`, latest) for **every** component, with stories for each state, a dark-sheet background decorator, and a `prefers-reduced-motion` toggle. `npm run storybook:build` runs in CI. (Owner's standing rule.)
- Styling: CSS Modules + CSS custom properties generated from `design/tokens.json` (no Tailwind needed). Self-hosted fonts via `@fontsource-variable/*`. **Zero third-party requests** on any page: no Google Fonts, no CDNs, no trackers.
- Content: Astro content collections (MDX) for `docs/`, `compare/` and `guides/`.
- Tests: Playwright smoke + visual snapshots at 390/768/1440 widths; `html-validate`; link check; **Lighthouse CI** budgets (mobile Performance ≥ 95, Accessibility ≥ 100, SEO 100, LCP ≤ 2.0 s, CLS < 0.05, home JS ≤ 60 KB gzip).
- Deploy: `.github/workflows/pages.yml` (official `withastro/action` + `actions/deploy-pages`). Owner sets Settings → Pages → Source = GitHub Actions. `astro.config.mjs`: `site: 'https://tanzir71.github.io', base: '/saydraft'` until G6. After G6, `site: 'https://saydraft.app', base: '/'` + `public/CNAME` (GitHub then redirects the github.io URL to the custom domain automatically).

```
site/
  astro.config.mjs, package.json, .storybook/
  src/components/<Name>/<Name>.tsx, <Name>.module.css, <Name>.stories.tsx
  src/layouts/Base.astro (SEO head), Doc.astro, Compare.astro
  src/pages/ (see 9.5)   src/content/{docs,compare,guides}/*.mdx
  src/assets/photo/ (G10)  public/{robots.txt,llms.txt,favicon.svg,og/}
design/tokens.json  → build step emits site/src/styles/tokens.css and saydraft/ui/theme/tokens.qss
```

### 9.4 Component library (each with stories)

`NavPill` (wordmark, links, CTA; collapses to a sheet menu on mobile) · `Button` (primary ink, secondary paper, on-dark) · `Eyebrow` · `SerifHeading` (supports `<em>` emphasis) · `Sheet` (variant night/deep/paper/raised; stacked top radius; overlap) · `Ribbon` (SVG `textPath`, animated `startOffset`, reduced-motion = static) · `BarDemo` (a pure-CSS replica of the Saydraft Bar with listening/cleaning/inserted states, driven by props) · `EditChip` · `BeforeAfterCard` (messy → clean with chips) · `FeatureRow` (visual left, serif title + one line right; scroll-highlight) · `StyleSwitcher` (same sentence in Formal/Casual/Very casual) · `KeyCaps` · `StatBlock` · `PrivacyFacts` · `CompareTable` (dated, sourced cells) · `FAQ` · `DownloadCard` (winget command copy, SHA-256, size) · `CreditsBand` · `Footer` · `AnnouncementBar` · `DocLayout` parts (TOC, callout, code block with copy).

### 9.5 Information architecture (URL slugs carry the keywords, §10)

| URL | Purpose |
|---|---|
| `/` | Home (sections in 9.6) |
| `/download/` | Installer, winget/Scoop commands, checksums, requirements, model sizes |
| `/wispr-flow-alternative/` | Factual comparison + migration guide (same shortcuts!) |
| `/typeless-alternative/` | Comparison focused on offline use + Translate/Ask equivalents |
| `/superwhisper-alternative-windows/` | Comparison for Windows users |
| `/windows-voice-typing-alternative/` | vs Win+H (Windows voice typing needs the internet; Copilot+ PCs add on-device "fluid dictation") |
| `/dragon-alternative/` | Free alternative for Dragon users (accessibility/RSI angle) |
| `/offline-dictation-windows/` | Pillar guide: how offline dictation works, models, hardware, privacy |
| `/dictation-for-developers/` | Voice coding: Cursor, VS Code, Claude Code, Codex; code mode |
| `/docs/…` | getting-started, shortcuts, styles, dictionary, models, languages, command-mode, privacy/verify-offline, troubleshooting, faq |
| `/changelog/` | Generated at build from GitHub Releases |
| `/credits/` | Model and library licenses and attributions (required for CC-BY-4.0) |
| `/privacy/` | Site (no tracking) + app (no network) policy |
| `/demo/` | Port of the existing canned simulation (noindex) |

### 9.6 Home page, section by section (copy is a starting point; claims must be sourced or measured)

1. **AnnouncementBar** (deep): "Saydraft 1.0: on-device AI cleanup. Free and open source →"
2. **NavPill:** wordmark · Features · Compare · Docs · GitHub · **Download for Windows**
3. **Hero** (paper): eyebrow `OFFLINE DICTATION FOR WINDOWS` · H1 "Speak messy. *Paste polished.*" · sub "Free, open-source voice typing that cleans up your words on your PC. No cloud, no account, no word limits." · CTA + "View on GitHub" · meta line "Windows 10 & 11 · works with Wi-Fi off". Visual: `Ribbon` → `BarDemo` → clean text with `EditChip`s.
4. **CreditsBand** (night sheet): "Built on open models" + wordmarks as text + the star count.
5. **Speed** (deep sheet): serif stat. Use only a **sourced** speaking-vs-typing figure, or our own measured WPM from the eval harness with a methodology link. If neither exists, use a qualitative line ("Talk at the speed you think"). The visual is a photo with the bar.
6. **"Edits as you speak"** (paper): three `BeforeAfterCard`s: Backtrack ("coffee at 2… actually 3"), Fillers, Lists.
7. **"Built around how you write"** (paper): `FeatureRow`s: Styles per app (`StyleSwitcher`), Dictionary that learns, Snippets, Command Mode, 25+ languages with auto-detect plus 99 with the all-languages model, Live preview (Labs).
8. **Same shortcuts, zero relearning** (raised card): `KeyCaps` for Ctrl+Win, Ctrl+Win+Space, Shift+Alt+Z. "Coming from Wispr Flow? Your fingers already know Saydraft." (factual, no logo)
9. **Privacy** (raised card): "Your voice *never leaves this PC.*" + `PrivacyFacts` + "Verify it yourself →" (docs: Wi-Fi off test, Resource Monitor, firewall rule).
10. **Compare** (paper): `CompareTable` Saydraft vs Wispr Flow vs Typeless vs Windows voice typing. Each cell dated and linked; footnote "Not affiliated with Wispr or Typeless. Info as of <date>."
11. **FAQ** (paper): 8–10 questions (also FAQPage schema).
12. **Final CTA** (full-bleed photo sheet with bottom radii): "Your words. *Your machine.*" + Download.
13. **Footer** (paper): product cards (Dictation, Notes) as flat colour tiles; columns Product · Compare · Docs · Project (GitHub, License, Credits, Changelog) · "Made in Dhaka" (optional, owner's call).

### 9.7 Assets policy
- Photos: owner-sourced (G10). Art direction: candid person mid-sentence or walking, warm late light, heavy horizontal motion blur, no sharp faces, 3:2, AVIF + WebP at 640/1280/1920 widths. Until then, use flat duotone gradient placeholders from tokens.
- Product shots: real screenshots of the Hub and Bar at 2× (from the Qt gallery, P6.6).
- Icons: one stroke family (Lucide, ISC license) at 1.5 px. No competitor marks anywhere.
- OG images: generated at build (title + serif + paper), 1200×630, one per page.

---

## 10. SEO plan (keywords at every touchpoint)

### 10.1 Keyword clusters (intent evidence = phrases that competitors and listing sites currently target and rank for; validate volumes in Search Console after launch)

| Cluster | Primary phrases | Secondary / long tail | Target page |
|---|---|---|---|
| **Brand** | saydraft, saydraft dictation, saydraft windows | saydraft download, saydraft github | `/`, `/download/` |
| **Competitor alternative** | wispr flow alternative · free wispr flow alternative · open source wispr flow alternative · wispr flow alternative windows | offline wispr flow alternative, wispr flow alternative github, wispr flow without subscription, wispr flow free limit | `/wispr-flow-alternative/` |
| | typeless alternative · typeless offline | typeless free alternative, typeless word limit | `/typeless-alternative/` |
| | superwhisper for windows · superwhisper alternative windows | free superwhisper alternative | `/superwhisper-alternative-windows/` |
| | dragon naturallyspeaking alternative free | dragon alternative windows 11, free dictation for rsi | `/dragon-alternative/` |
| **Category head terms** | offline dictation software windows · voice typing windows 11 · speech to text windows offline | free dictation software windows, ai dictation app windows, voice to text app windows, private speech to text, local speech to text app | `/`, `/offline-dictation-windows/` |
| **Built-in comparison** | windows voice typing offline · win+h alternative | windows voice typing without internet, better than windows dictation, voice typing removes filler words | `/windows-voice-typing-alternative/` |
| **Technical long tail** | parakeet dictation windows · whisper dictation windows · local whisper push to talk | faster-whisper dictation app, offline voice typing with ai cleanup, dictation that removes um, llama.cpp dictation cleanup | `/offline-dictation-windows/`, docs, blog |
| **Developers** | voice coding windows · dictation for cursor · voice to text for claude code | voice prompt coding, vibe coding with voice, dictate commit messages | `/dictation-for-developers/` |
| **Accessibility** | dictation software for rsi · hands free typing windows | speech to text for disabilities free | `/dragon-alternative/`, docs |

### 10.2 Touchpoint map (Codex implements; the owner applies GitHub settings or approves `gh` commands)

| Touchpoint | Exact content / rule |
|---|---|
| **Repo name** | `saydraft` (G1) |
| **Repo description** (≤ 350 chars) | "Free, open-source offline dictation for Windows. Hold a key, speak, get clean formatted text in any app. Local Parakeet/Whisper speech-to-text + on-device AI cleanup. A private Wispr Flow / Typeless alternative." |
| **Repo website field** | Pages URL (or `saydraft.app` after G6) |
| **Topics** (max 20, lowercase-hyphen) | `dictation` `speech-to-text` `voice-typing` `voice-to-text` `offline` `windows` `wispr-flow-alternative` `typeless-alternative` `whisper` `parakeet` `local-llm` `llama-cpp` `sherpa-onnx` `privacy` `accessibility` `push-to-talk` `transcription` `asr` `pyside6` `productivity` |
| **Social preview** | 1280×640 from the OG generator: "Saydraft: offline dictation for Windows" |
| **README H1 + first paragraph** | H1 "Saydraft: free offline dictation for Windows". The first 160 chars repeat the description's primary terms. Then a GIF of the Bar, a download badge, a "Coming from Wispr Flow or Typeless?" section, the comparison table (dated), FAQ, and credits |
| **Releases** | Title "Saydraft vX.Y: offline AI dictation for Windows"; assets `Saydraft-Setup-X.Y.Z-x64.exe`, `SHA256SUMS.txt`; notes start with user-facing changes |
| **winget** | `Tanzir.Saydraft`; ShortDescription "Free offline AI dictation for Windows"; Tags `dictation, speech-to-text, voice-typing, offline, wispr-flow-alternative, accessibility` |
| **Scoop** | `extras`-style manifest in a `scoop-saydraft` bucket |
| **Site `<title>`** (≤ 60 chars) | Home: "Saydraft: Free Offline AI Dictation for Windows". Compare pages: "Free Offline {Competitor} Alternative for Windows · Saydraft". Guides: "{Topic} on Windows (2026 Guide) · Saydraft" |
| **Meta description** (≤ 155) | Unique per page, with a primary phrase + benefit + "free, open source" |
| **H1 / H2** | One H1 per page containing the page's primary phrase; H2s carry the secondary phrases naturally |
| **URLs** | Exactly the §9.5 slugs (lowercase, hyphenated, keyword-first) |
| **Images** | Descriptive filenames + alt text ("saydraft-bar-listening-windows-11.avif") |
| **Structured data** | `SoftwareApplication` (name, operatingSystem "Windows 10, Windows 11", applicationCategory "UtilitiesApplication", offers price 0, license URL, downloadUrl, softwareVersion), `FAQPage` on Home and compare pages, `BreadcrumbList` on docs, `Organization`/`Person` (Tanzir Rahman) on About/credits |
| **Technical** | `sitemap-index.xml` (@astrojs/sitemap), `robots.txt` with the sitemap, canonical on every page, `hreflang` not needed (English), custom `404`, `llms.txt` + `llms-full.txt`, OG/Twitter cards, `<meta name="theme-color">` |
| **Internal links** | Every compare page links to `/download/`, the pillar guide and two docs pages; the home page links to all compare pages in the Compare section and the footer |
| **App itself** | About → "saydraft.app" link (opens the browser only on click; no network from the app); the installer's Start menu shortcut description uses "Saydraft: offline dictation" |
| **Webmaster tools** | Owner verifies Google Search Console + Bing Webmaster Tools (meta tag via env var at build); IndexNow key file in `public/` |
| **Listings** (drafts in `docs/launch/`; owner posts) | AlternativeTo (as an alternative to Wispr Flow, Typeless, Superwhisper, Dragon, Windows Speech Recognition), opensourcealternatives.to, openalternative.co, Product Hunt, Show HN, r/windowsapps, r/LocalLLaMA; PRs to relevant awesome lists |

### 10.3 Content rules
- Never claim certifications or stats we can't show. Competitor facts carry "as of {date}" + a source link; re-verify each quarter (add a `content/compare/*.mdx` frontmatter `verified:` date and fail the build if it's older than 120 days).
- Technical content outranks fluff for this audience (the owner prefers tools and how-tos over opinion): publish `guides/parakeet-vs-whisper-windows-cpu` with our own bench numbers, `guides/verify-offline-dictation`, and `guides/voice-coding-cursor-claude-code`.

---

## 11. Evaluation and QA (the regression net for every milestone)

| Suite | Content | Gate |
|---|---|---|
| **Cleanup golden set** | Grow `tests/eval_corpus.jsonl` from 42 to **≥ 300** cases: fillers, backtrack positives/negatives, lists, spoken punctuation, ITN, emails/URLs, code mode, messaging period rule, "press enter", snippets, profanity kept, multilingual (EN, ES, DE), **code-switching EN+AR and EN+BN**, long (≥ 120 words) | Rules-only ≥ 90%; rules+LLM (Standard) ≥ 92% with **0 regressions vs rules-only** on must-keep cases |
| **Adversarial LLM set** | 100 dictations that look like instructions or questions | "Answered instead of cleaned" = **0** (validator catches 100%) |
| **ASR WER** | `eval/audio/`: owner-recorded 60 clips (quiet, noisy, fast, accented, whispered, names), plus a script that downloads a LibriSpeech test-clean subset at dev time | Parakeet v3 relative WER ≤ 0.6 × Whisper base on the owner clips |
| **Latency** | `tools/bench.py`: release→text p50/p95 per tier for 3/10/30/90 s clips, cold and warm | §1 row 8 budgets |
| **Insertion matrix** | Manual + scripted: Notepad, Word, Outlook, Chrome textarea, Gmail, Slack desktop, Teams, WhatsApp desktop, VS Code, Cursor, Windows Terminal, PowerShell ISE, Notion, Obsidian, an elevated cmd (expect the "admin window" message), a password field (expect refusal) | All expected |
| **Parity A/B** (owner, optional) | Dictate the same 30 utterances into Wispr Flow (free tier) and Saydraft; blind-score cleanliness 1–5 | Saydraft mean ≥ 4.0 and within 0.3 of Wispr |
| **Offline proof** | `pytest -m offline`: NetworkGuard raises on any non-loopback connect during 50 synthetic dictations | Must pass |
| **Soak** | `tools/soak.py` 200 cycles | RSS growth < 10%, 0 stuck clipboards, 0 orphan sidecars |

---

## 12. Loop State: milestones and tasks

> Order is deliberate: P0 hygiene → P2 refactor → P3/P4 quality (biggest user-visible gap) → P5/P6 feel → P7 power features → P8 distribution → P9 site/SEO. P1 (rename) runs as soon as **G1** is approved. P9.1–P9.2 (site scaffold + components) may run in parallel with P3+ because they don't touch app code.

### P0: Foundations
- [x] **P0.1** `git mv CODEX_HANDOFF.md docs/history/CODEX_HANDOFF_v1.md`; keep this file at the root; add `docs/README.md` explaining the doc set. **Acceptance:** old file reachable at the new path; history intact (`git log --follow`).
- [x] **P0.2** Repo hygiene: add a full `.gitignore` (Python, PyInstaller `build/` `dist/`, `__pycache__/`, `*.pyc`, `models/`, `.venv/`, `site/node_modules/`, `site/dist/`, `.vercel`). Run `git rm -r --cached dist build` and `git rm -r --cached '**/__pycache__'`. **Files stay on disk.** **Acceptance:** `git ls-files | grep -E '^(dist|build)/' | wc -l` = 0; local `dist/` still exists. *(P0.2b history purge only if G4 approved.)*
- [ ] **P0.3** (G2) Add `LICENSE` and `THIRD_PARTY_NOTICES.md` (PySide6 LGPL-3.0 dynamic-link note, faster-whisper/CTranslate2 MIT, sherpa-onnx Apache-2.0, onnxruntime MIT, llama.cpp MIT, model licenses table). **Acceptance:** a license is detected on the GitHub repo page.
- [ ] **P0.4** CI `.github/workflows/ci.yml` on `windows-latest`: Python 3.13, `pip install -r requirements-dev.txt`, `ruff`, `pytest` (offscreen Qt), eval; cache pip. **Acceptance:** green on main; the README badge works.
- [x] **P0.5** `tools/bench.py` + `docs/BASELINE.md`: record current latency per stage and RAM on the owner machine (owner runs it, Codex writes the tool). **Acceptance:** the baseline table is committed.
- [x] **P0.6** `privacy/netguard.py`: wrap `socket.socket.connect`/`create_connection` and `getaddrinfo`; allow loopback; allow downloader sessions only inside a `with NetworkGuard.allow_downloads(manifest_hosts)` context; block and log everything else. Install it at startup. **Acceptance:** `pytest -m offline` passes; a test proves a stray `urllib.request.urlopen('https://example.com')` raises.

P0.3/P0.4 implementation is locally verified and published in draft PR #1. Hosted Windows CI passed on the PR and branch (runs 43075796248 and 43075669613). Final main-branch acceptance (license detection and green CI on main) awaits owner review/merge; this is the reason these two boxes remain unchecked.

### P1: Rename to Saydraft (G1 approved 2026-11-12)
- [x] **P1.1** Package rename + shim + spec/exe/AUMID (§5.2 step 1). **Acceptance:** `python -m saydraft` runs; `python -m voicetray` prints a deprecation warning and runs; all tests pass.
- [x] **P1.2** Data migration (copy) + autostart + mutex (§5.2 steps 2–3). **Acceptance:** a test fixture with an old dir migrates idempotently; the old dir is unchanged byte-for-byte.
- [x] **P1.3** Strings/assets/README/llms.txt/docs. **Acceptance:** `rg -i voicetray --glob '!docs/history/**' --glob '!saydraft/compat/**'` returns only intended compatibility hits.
- [x] **P1.4** Owner runs (or approves Codex running) the GitHub rename + remote update (§5.2 steps 5–6). **Acceptance:** `git remote -v` shows `saydraft`; the old URL redirects.

### P2: Core refactor (retire `legacy_app.py`)
- [x] **P2.1** `core/session.py`: a pure state machine (`Idle → Arming → Listening → Finalizing → Cleaning → Inserting → Done | NotInserted | Error | Cancelled`) with an injected clock; every transition emits an event. **Acceptance:** ≥ 40 table-driven tests including cancel at every state, the 0.5 s discard, and a hotkey bounce.
- [ ] **P2.2** Interfaces (`AsrEngine`, `StreamingAsrEngine`, `Cleaner`, `Formatter`, `Inserter`, `ContextProvider`, `HistoryStore`) + a DI container; move behaviour out of `legacy_app.py` into services; remove `legacy_app.py` **in a git commit** once tests are green. **Acceptance:** no import of `legacy_app` remains; tests are green; manual dictation into Notepad works.
  - Implementation complete in the p2-services branch: injected ports/container, serial session worker, preserved history/fallbacks, retired module removed, native Unicode fallback fixed. 305 tests pass, eval 42/42, real cached-ASR fixture inserted exactly into Notepad; 200-cycle service soak passes. Acceptance still pending: owner live-microphone dictation check (fixture-driven Windows check is documented in docs/CORE_REFACTOR.md). Continuing P2.3 independently while that manual check remains open.
- [x] **P2.3** Background segment transcription during speech (VAD segment queue) wired through the session. **Acceptance:** for a 60 s fixture, release→raw text ≤ 1.3 × the time to transcribe only the last segment.
- [x] **P2.4** `data/db.py` migrations v2: history columns (`app_exe`, `app_group`, `style`, `intensity`, `language`, `asr_model`, `llm_model`, `llm_decision`, `timings_json`, `edits_json`, `audio_path`), plus tables `dictionary`, `snippets`, `styles`, `stats_daily`. Import `glossary.json`, `snippets.txt` and `app_profiles.json` by **copying** (originals untouched). Write a `history.db.bak-<date>` before migrating. **Acceptance:** a migration test on a copy of a real v1 DB keeps the row count and every raw/cleaned text identical.

### P3: Recognition quality
- [x] **P3.1** Add `sherpa-onnx` (pin ≥ 1.13.4) + Silero VAD; keep webrtcvad as the fallback. **Acceptance:** a VAD unit test on silent/speech fixtures; no regression in the silence-skip tests.
- [ ] **P3.2** `models/manifest.json` + resumable SHA-256 downloader + license display; `asr/sherpa_parakeet.py` (Parakeet TDT 0.6B v3 int8 default; v2 English-max). **Acceptance:** the `hello.wav` fixture transcribes; WER on owner clips is recorded in `docs/MODELS.md`; a cold load ≤ 3 s is logged.
- [ ] **P3.3** Upgrade `whisper_ct2.py` to support `large-v3-turbo` (int8) as the "All languages" model; keep base/small. **Acceptance:** Bengali and Arabic smoke fixtures produce script-correct output.
- [ ] **P3.4** `asr/router.py` (§7.1 rules) + Settings → Languages (Auto or pin up to 3). **Acceptance:** router unit tests for every rule; an "Retry with All-languages model" action exists on history rows with audio.
- [ ] **P3.5** Biasing spike (§7.1) → `docs/spikes/biasing.md` with numbers; then implement the winning path + phonetic post-correction. **Acceptance:** dictionary-term recall on a 40-term test improves ≥ 30% relative vs no biasing.
- [ ] **P3.6** `models/hardware.py` probe + bench → tier; persisted; shown in Settings. **Acceptance:** deterministic tier tests with mocked timings.
- [ ] **P3.7** (Labs) `asr/sherpa_stream.py` Nemotron streaming + Bar live-preview strip. **Acceptance:** partials update ≥ 4×/s on the reference CPU; final text is still produced by the default offline engine unless "Use streaming result" is set.
- [ ] **P3.8** (Labs) Qwen3-ASR-0.6B evaluation spike → `docs/spikes/qwen3-asr.md` (WER on owner clips in EN/AR, RAM, latency). No ship decision without data.

### P4: Cleanup intelligence
- [ ] **P4.1** `cleanup/llm/sidecar.py`: download a pinned llama.cpp release (CPU + Vulkan builds), start/health-check/restart/idle-unload, random port + API key, loopback only; Job Object so it dies with the app. **Acceptance:** killing the sidecar mid-request yields rules output within budget; no orphan process after the app quits (soak).
- [ ] **P4.2** Prompt v3 (§7.3) in `cleanup/llm/prompts/`; streaming client; remove JSON output. **Acceptance:** a fake-LLM contract test; adversarial few-shots present.
- [ ] **P4.3** Validator v2 (§7.3). **Acceptance:** 100% catch on the adversarial set; unit tests per rule.
- [ ] **P4.4** Model bake-off (Qwen3.5 0.8B/2B/4B, Gemma 4 E2B/E4B) on the golden + adversarial sets + latency per tier → set defaults per tier in the manifest. **Acceptance:** `docs/MODELS.md` table; defaults justified by numbers.
- [ ] **P4.5** Deterministic upgrades (§7.4): commands, ITN, backtrack restatement, lists, messaging period, "press enter", code mode. **Acceptance:** ≥ 150 new golden cases pass in rules-only mode.
- [ ] **P4.6** Need-score + latency predictor + hard timeout; log the decision. **Acceptance:** the latency suite meets §1 row 8 on Standard and Pro.
- [ ] **P4.7** Golden set ≥ 300 + adversarial 100; CI thresholds enforced (§11).

### P5: Windows integration (the "it just works" feel)
- [ ] **P5.1** `hotkeys/llhook.py` (keyboard + mouse LL hooks), chords, Start-menu mask, mouse buttons, conflict detection (including a running Wispr Flow), defaults per §8.2; remove the `keyboard` dependency. **Acceptance:** chord tests with synthetic events; manual: Ctrl+Win never opens the Start menu; F9 legacy still works.
- [ ] **P5.2** `insert/clipboard_win.py` all-format snapshot/restore (skip formats that fail to render; cap at 64 MB), set `ExcludeClipboardContentFromMonitorProcessing`, `CanIncludeInClipboardHistory=0` and `CanUploadToCloudClipboard=0` on our writes; `SendInput` paste; typing fallback via `KEYEVENTF_UNICODE`; UIPI detection (target integrity > ours → NotInserted with a reason). **Acceptance:** a copied image and rich text survive a dictation; Win+V history shows no dictation entries.
- [ ] **P5.3** `context/`: foreground exe via `GetWindowThreadProcessId` + `QueryFullProcessImageNameW`; app groups (§8.3 defaults, user-editable); browser site from Chrome/Edge/Firefox titles; UIA focused element: `IsPassword`, ControlType, text before the caret (TextPattern/ValuePattern), selection. **Acceptance:** unit tests with mocked UIA; manual: a password field refuses insertion.
- [ ] **P5.4** `cleanup/formatter.py` caret-aware spacing/capitalization + messaging period rule. **Acceptance:** 30 golden cases with a `before_caret` context.
- [ ] **P5.5** Hands-free (chord + double-tap), Esc cancel, paste-last (Shift+Alt+Z), 0.5 s discard, 20-min soft cap with a warning at 19:00. **Acceptance:** session tests + manual check.
- [ ] **P5.6** Dictionary auto-learn (§8.5) + Undo toast + toggle. **Acceptance:** an alignment unit test suite; manual: correct "Kubernetes" in Notepad after dictation → suggestion appears.
- [ ] **P5.7** Styles engine: app group × tone × intensity → rule options + LLM header. **Acceptance:** golden cases per group/tone; the Hub preview matches the engine output.

### P6: UI parity
- [ ] **P6.1** (G3 for final values) `design/tokens.json` → `tokens.qss` generator; bundle the OFL fonts in the app; theme light/dark. **Acceptance:** the gallery renders in both themes; no drop shadows anywhere (`rg -n "QGraphicsDropShadowEffect"` = 0).
- [ ] **P6.2** Saydraft Bar v2 per §8.1 (states, sizes, sounds, multi-monitor, hide option, click to start). **Acceptance:** pytest-qt state tests + screenshot snapshots per state.
- [ ] **P6.3** Hub (§8.3) replacing the separate Settings and History windows (migrate their logic; delete the old windows **in a commit** once parity tests pass). **Acceptance:** every Settings field is preserved; History supports the diff, retry and export.
- [ ] **P6.4** Onboarding v2 (§8.4) with the sandbox. **Acceptance:** a first-run test path with mocked downloads; manual run under 3 minutes on a fresh profile.
- [ ] **P6.5** Scratchpad (Win+Alt+S) + View diff (Ctrl+Win+D). **Acceptance:** chords work; the scratchpad persists to Notes.
- [ ] **P6.6** `python -m saydraft.ui.gallery`: every widget in every state (Bar states, toasts, Hub pages with fixture data, onboarding steps). Generate PNGs for the site's product shots. **Acceptance:** `pytest -m gallery` snapshot tests.
- [ ] **P6.7** Accessibility pass (tab order, accessible names, high contrast, 200% scaling). **Acceptance:** checklist in `docs/TEST_CHECKLIST.md` passes.

### P7: Power features (tier-gated; Labs toggles)
- [ ] **P7.1** Command Mode (Ctrl+Win+Alt): read the selection via UIA (fall back to Ctrl+C with a clipboard snapshot), plus the instruction, to the LLM (Pro tier; Standard shows "Needs Pro tier" with an explanation); replace via paste; if replacement fails, show a Scratchpad popup with Copy. Esc cancels. **Acceptance:** 30 instruction cases ("shorter", "more formal", "bullets", "translate to Spanish") pass the validator's edit-mode rules.
- [ ] **P7.2** Translate mode (target language per hotkey or Style) via the LLM; mark it Labs. **Acceptance:** EN↔ES and EN↔AR smoke cases.
- [ ] **P7.3** Ask about the selection (summarize/explain/rewrite → Scratchpad answer); never web. **Acceptance:** works on read-only text (browser article selection).
- [ ] **P7.4** Whisper mode: input gain + AGC + speech enhancement (sherpa-onnx GTCRN if available) + VAD threshold profile. **Acceptance:** WER on the whispered owner clips improves ≥ 20% relative vs off.
- [ ] **P7.5** Notetaker (§8.6). **Acceptance:** a 30-min test meeting produces a Markdown note with speakers + summary + next steps fully offline; the NetworkGuard test passes during capture.

### P8: Distribution and trust
- [ ] **P8.1** Clean-venv build script (`tools/build.ps1` rewrite: fresh venv, `requirements.txt` only, exclusion list), plus an Inno Setup per-user installer (no admin), Start menu entry, optional autostart, and an uninstaller that **keeps user data unless the user ticks "Also remove my data"**. **Acceptance:** installer ≤ 250 MB; `pyarrow`/`aiohttp` absent from the bundle.
- [ ] **P8.2** `release.yml`: on tag `v*` → build → SHA256SUMS → draft GitHub Release with notes. **Acceptance:** a dry-run tag produces a draft.
- [ ] **P8.3** (G5) Signing in the release workflow. **Acceptance:** a signed installer verifies with `signtool verify /pa`.
- [ ] **P8.4** winget manifest PR (`Tanzir.Saydraft`) + Scoop bucket. **Acceptance:** `winget install Tanzir.Saydraft` works after the PR merges (owner submits).
- [ ] **P8.5** Opt-in update check (default **off**), GitHub Releases API only, shows a notice and opens the release page; never auto-downloads. **Acceptance:** the NetworkGuard test passes with it off; it works when on.
- [ ] **P8.6** Privacy extras: Settings → Privacy "Block Saydraft from the internet" creates/removes a Windows Firewall outbound rule for `Saydraft.exe` (UAC prompt; explains that model downloads then need the rule off); "Verify offline" docs page. **Acceptance:** with the rule on, dictation works and downloads fail with a clear message.

### P9: Website on GitHub Pages + SEO
- [ ] **P9.0** (G3) Visual lock: owner approves §9.2 tokens or provides Figma frames (hero, one feature row, compare table, mobile nav). Codex may proceed with P9.1–P9.2 using provisional tokens.
- [ ] **P9.1** `site/` scaffold: Astro + React + Storybook + tokens build + fonts + Playwright + Lighthouse CI + `pages.yml`. Move the current `index.html` and `demo/` to `_archive/site-v1/` **via git mv** and port `demo/` to `/demo/`. **Acceptance:** Pages preview deploys from a branch workflow run; Storybook builds.
- [ ] **P9.2** Component library (§9.4) with stories for every state. **Acceptance:** `storybook:build` passes; visual snapshots committed.
- [ ] **P9.3** Home page (§9.6) with Ribbon/BarDemo motion + reduced-motion fallbacks. **Acceptance:** Lighthouse budgets met; zero third-party requests (Playwright asserts that every request host = site host).
- [ ] **P9.4** Compare pages, pillar guide, developers page, docs, download, credits, privacy, changelog (§9.5) with MDX + `verified:` frontmatter. **Acceptance:** each page has a unique title/description/H1 per §10.2; the build fails on stale `verified` dates.
- [ ] **P9.5** Technical SEO (§10.2 rows "Structured data", "Technical", "Webmaster tools"); OG image generation. **Acceptance:** Rich Results Test passes for SoftwareApplication + FAQPage on 3 pages; the sitemap lists every indexable URL.
- [ ] **P9.6** (G1) GitHub repo SEO: prepare `docs/launch/github-settings.md` with the exact description, topics, website and social preview, plus the `gh repo edit` commands. Owner runs them or approves Codex running them. README restructure per §10.2. **Acceptance:** repo page shows the topics and description.
- [ ] **P9.7** (G9) Old Vercel site: replace its `index.html` with a minimal page (banner "VoiceTray is now Saydraft" + canonical + link). **Don't remove the Vercel project or `vercel.json`** without approval. **Acceptance:** the old URL shows the banner.
- [ ] **P9.8** Launch kit in `docs/launch/`: AlternativeTo, Product Hunt, Show HN, Reddit and awesome-list drafts (factual, no superlatives). Owner posts.

### P10: Labs (only after P0–P9, and only with gates)
- [ ] **P10.1** (G7) Custom cleanup LoRA on Qwen3.5-0.8B: synthetic messy↔clean pairs (generated once at dev time), held-out eval, GGUF export. Ship only if it beats the P4.4 default on golden + adversarial at equal or better latency.
- [ ] **P10.2** In-browser demo on the site using a WebGPU Parakeet export (try your voice, nothing uploaded) if the bundle stays ≤ 10 MB before model fetch and the model loads only on click.

---

## 13. Non-goals (v1)

Cloud anything (sync, accounts, team dictionaries, web search in Ask), mobile apps, macOS/Linux builds (keep code portable), bots that join meetings, "Hey Flow"-style wake word (power and false-trigger cost), learning a user's writing style from their sent messages (privacy-heavy; revisit later), and any telemetry.

## Open Questions
- 2026-11-12: The legacy worker silently suppressed repeated dictations and inserted even after history write failures. P2.2 removes suppression and refuses insertion unless persistence succeeds, retaining failed raw/cleaned results for session recovery. This resolves a conflict with the hard constraints.
- 2026-11-12: P0.5 measured warm release-to-simulated-insertion p50 1.865 s / p95 2.447 s and first-use 24.664 s for base on the bundled 3 s clip. These exceed parity budgets; keep this as the pre-refactor baseline, not a performance claim. Native networking and subprocesses require the later OS firewall boundary.
<!-- Codex: add dated questions here instead of guessing. -->

---

## 14. Changelog
- 2026-11-12 | P3.1 | Pinned sherpa-onnx 1.13.4; added verified Silero v5 with MIT display, asynchronous download and WebRTC fallback; disabled native/Python runtime telemetry before model use. Real offline VAD smoke: 0.277 s load, speech retained, silence skipped. Full suite 332 pass, 1 skip; eval 42/42. CI now fetches the pinned VAD fixture before native offline tests. | saydraft/audio/vad_silero.py, saydraft/privacy/telemetry.py, saydraft/models/manifest.json, saydraft/ui/, requirements.txt, tests/, .github/workflows/ci.yml, docs/VAD.md
- 2026-11-12 | P2.4 | Added transactional SQLite v2 with retained pre-migration backups, metadata columns, dictionary/snippet/style imports and daily stats. Copy of actual runtime v1 DB retained its row count and all raw/cleaned text; source bytes unchanged. Tests cover WAL, rollback, unknown owner data and idempotence. Full suite 323 pass, 1 skip; eval 42/42; 200-cycle soak passes with 0.4% RSS growth. | saydraft/data/db.py, saydraft/history.py, saydraft/core/, tests/test_data_migrations.py, docs/DATABASE.md
- 2026-11-12 | P2.3 | Added background VAD segment recognition with whole-recording fallback and session cancellation; fixed reused capture buffers. Real-time 60 s cached-base benchmark: 14 segments pre-release; release→raw 0.841 s vs 1.073 s budget. Full suite 315 pass, 1 skip; eval 42/42. | saydraft/core/segments.py, saydraft/core/worker.py, saydraft/audio/, saydraft/config.py, tests/test_segments.py, tools/bench_segments.py, docs/SEGMENT_BENCHMARK.md
- 2026-11-12 | P2.1 | Added pure lifecycle state machine with injected clock, immutable transition events and generation checks; covers cancellation at every state, <0.5 s discard, slow arming, hotkey bounce and stale worker results with 56 tests. Full suite 288 pass, 1 skip; eval 42/42. | saydraft/core/session.py, tests/test_session.py
- 2026-11-12 | P1.4 | Executed the owner-approved GitHub rename to tanzir71/saydraft and updated origin; verified the old repository API redirects to the new full name. Existing releases, branches, settings and Vercel project were retained. | GitHub repository name, local origin remote
- 2026-11-12 | P1.1–P1.3 | Renamed package, application classes, launchers, spec, build metadata, AUMID, tests and docs to Saydraft; retained the deprecated module launcher. Added resumable copy-only profile migration, guarded autostart migration, per-user editable files, and a Windows named singleton. 232 tests pass; eval 42/42; real Qt launcher smoke exits cleanly on an isolated profile. Existing site URLs and historical docs intentionally retain the old name until their later tasks. | saydraft/, voicetray/, tests/, tools/, Saydraft.spec, run_app.bat, run_debug.bat, docs/DATA_MIGRATION.md, readme.md, llms.txt
- 2026-11-12 | P0.5 | Added reproducible cold/warm stage and RSS benchmarking; committed measured base/3 s results; fixed SQLite connection lifetime and the Windows soak RSS probe. | tools/bench.py, tools/soak.py, docs/BASELINE.md, tests/test_bench.py, voicetray/history.py
- 2026-11-12 | P0.6 | Installed offline socket policy at startup; scoped explicit model downloads to pinned hosts/revisions with SHA-256 verification and archived corrupt files; removed transcript text from INFO logs. 225 tests pass, 19 offline tests, eval 42/42; 200-cycle soak 0.3% RSS growth. | voicetray/privacy/, voicetray/models/, voicetray/model_download.py, voicetray/main.py, tests/test_netguard.py, tests/test_verified_downloader.py, docs/PRIVACY.md
- 2026-11-12 | P0.2 | Untracked 1,714 build artifacts and 28 bytecode files, preserving all files on disk; added Python, model, website and local-data ignores. Tests 199 pass, 1 skip; eval 42/42. | .gitignore, git index
<!-- Codex: one line per completed task: YYYY-MM-DD | task | summary | files -->
- 2026-11-12 | P0.1 | Archived the previous handoff with git mv; documented the active plan and retained history. Baseline: 199 tests pass, 1 optional integration skip; eval 42/42. | docs/README.md, docs/history/CODEX_HANDOFF_v1.md, WISPR_OFFLINE_PARITY_PLAN.md
- 2026-11-11 | — | Plan created from a repo audit + competitor/model/SEO research; supersedes CODEX_HANDOFF.md (to be archived in P0.1) | WISPR_OFFLINE_PARITY_PLAN.md

---

## 15. Sources (verify before quoting on the site)

**Wispr Flow:** homepage https://wisprflow.ai/ (fonts and colours inspected 2026-11-11) · What is Flow (internet required; Hub contents) https://docs.wisprflow.ai/articles/2772472373-what-is-flow · Shortcuts https://docs.wisprflow.ai/articles/2612050838-supported-unsupported-keyboard-hotkey-shortcuts · Default shortcuts / paste last https://docs.wisprflow.ai/articles/5298382595-route-dictation-directly-to-slack-email-or-calendar-with-keyboard-shortcuts · Hands-free https://docs.wisprflow.ai/articles/6391241694-use-flow-hands-free · Command Mode https://docs.wisprflow.ai/articles/4816967992-how-to-use-command-mode · Smart Formatting & Backtrack https://docs.wisprflow.ai/articles/5373093536-how-do-i-use-smart-formatting-backtrack · Free tier https://docs.wisprflow.ai/articles/4760791189 · Data controls https://wisprflow.ai/data-controls · Compiled UX reference (Flow Bar states, onboarding, styles) https://cdn.jsdelivr.net/npm/@agent-native/core@0.124.6/corpus/templates/clips/desktop/design-refs/wispr-ux.md · Pricing summary https://bossai.tech/blog/wispr-flow-for-windows

**Typeless:** homepage https://www.typeless.com/ · pricing https://www.typeless.com/pricing · free-tier change (third-party, competitor-authored) https://willowvoice.com/blog/typeless-wispr-flow-review

**Open source:** FreeFlow https://github.com/zachlatta/freeflow · Handy https://github.com/cjpais/Handy · OpenWhispr streaming write-up https://openwhispr.com/blog/local-streaming-speech-to-text · Parakeet vs Whisper vs Nemotron https://openwhispr.com/blog/parakeet-vs-whisper-vs-nemotron · Alternatives roundup https://www.assemblyai.com/blog/best-wispr-flow-alternatives

**Models and runtimes:** Open ASR Leaderboard roundups https://pinggy.io/blog/best_open_source_self_hosted_speech_to_text_models/ and https://apidog.com/blog/best-open-source-speech-to-text-models/ and https://benchmarklist.com/benchmarks/open_asr_leaderboard/ · onnx-asr (Parakeet v3, DirectML, CPU RTFx) https://pypi.org/project/onnx-asr/ · sherpa-onnx https://github.com/k2-fsa/sherpa-onnx · Nemotron streaming EN license https://huggingface.co/nvidia/nemotron-speech-streaming-en-0.6b · Nemotron 3.5 streaming https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b · Qwen3-ASR report https://arxiv.org/abs/2601.21337 · Qwen3-ASR CPU ONNX https://huggingface.co/Daumee/Qwen3-ASR-0.6B-ONNX-CPU · Qwen3.5 small models https://unsloth.ai/docs/models/qwen3.5 · Dictation-cleanup LLM bench https://www.assemblyai.com/blog/best-llms-dictation-cleanup · s1-mini (custom license) https://betterstack.com/community/guides/ai/s1-mini/

**Windows landscape / SEO intent:** https://spokenly.app/blog/best-dictation-software-windows · https://superwhisper.com/windows · https://openwhispr.com/blog/best-dictation-tools-windows-2026 · https://www.opensourcealternatives.to/alternative-to/wispr-flow · https://alternativeto.net/software/superwhisper/

**Name checks (2026-11-11):** GitHub repository search via API (`saydraft`: 0 results) · registrar availability lookup (`saydraft.app/.dev/.org` available; `.com` taken) · existing products: Sotto https://www.everydev.ai/tools/sotto/llms.txt · Kotha https://apps.apple.com/us/app/kotha/id1188060798

