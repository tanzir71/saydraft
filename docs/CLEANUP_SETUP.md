# Verified cleanup setup

The app catalog now includes the exact measured Qwen3.5 0.8B and 2B Q4_K_M
artifacts, their original conversion cards and the bundled Apache-2.0 notice.
They use the existing pinned llama.cpp b12110 CPU or Vulkan runtime. Importing
the catalog or asking for a recommendation performs no downloads or inference.

The manifest recommends rules for Lite, 0.8B for measured Standard hardware and
2B for Pro. Pending measurements select neither model. Recommendations never
enable cleanup, change an existing path or begin installation. A Vulkan device
in the saved hardware report recommends that runtime; otherwise CPU is offered.
Standard still requires ASR ≤1.2 s and 0.8B ≥25 tokens/s, and low RAM/slow ASR
keeps Lite. The co-loaded development CPU measured 21.2 tokens/s and remains
Lite; no CPU Standard latency acceptance is claimed.

Selection follows the five-artifact bake-off in [Models](MODELS.md): 0.8B scores
431/432 strict golden cases and 2B scores 429/432, both with zero finite native
preservation-guard failures across 100 adversarial inputs. Pro chooses the smallest model in the spec's
2B–4B range: its 302 accepted exact cases beat 0.8B's 297 in the common forced
comparison, while 4B/Gemma artifacts show no quality benefit on this corpus.
The gated RTX recipe subsequently scores 432/432 with 213 accepted replies.
These are corpus/artifact results, not owner accuracy or broad power-feature
acceptance. Subsequent runtime changes still require current-source policy
evidence before the mandatory native CI gate can be enabled.

`cleanup_bundle(model_id, backend)` provides both licensed components and exact
transfer sizes, including the runtime archive rather than its unpacked size.
`download_cleanup_model` is an explicit action. It installs the selected model
and runtime with aggregate progress and the existing pause/resume behavior.
No optional language model is included in this package.

New model storage is `models/llm/<id>/<revision>/`. Resumable files stay in a
sibling `.download` directory. All weight/card/notice hashes must pass before
the complete directory is renamed into place. A changed existing directory is
retained under `_archive`; earlier revisions remain untouched. Move destinations
are checked against the resolved storage root, including archive junctions.
Both model and runtime must verify before the helper returns a usable GGUF path.
A failed runtime installation retains the completed model for a later retry.

Bundled notices are constrained to `assets/licenses`, checked before any weight
transfer, copied locally and included in the completion receipt. They never
cause an extra HTTP request. A repeated setup reuses verified files. UI controls
and applying the downloaded model follow in the next change; existing manual
GGUF paths remain available throughout this foundation.

Unit verification covers exact catalog pins, recommendations, both runtime
choices, license path/hash checks, complete installation, cache reuse, failed
transfer recovery, pause before setup and preservation of changed/older files.
The native setup probe seeds fresh QA storage using hard links to previously
verified caches, forbids HTTP, invokes the real installer twice and measures the
owned loaded decoder. It writes only a new directory and changes no user profile:

```powershell
python -m tools.probe_cleanup_setup --model qwen35-2b-q4-k-m --backend vulkan --candidate-cache D:\QA\cleanup-candidates --runtime-cache D:\QA\llama-cpp-b12110-vulkan-x64 --output D:\QA\New-Cleanup-Setup
```

Validation: 1496 tests pass with four optional native skips, rules 432/432,
authored adversarial checks 100/100, Ruff and diff checks pass. Native cached
installation and inference proof follows separately; UI work remains pending.

Clean immutable `42c28d1` native checks now pass for both 0.8B/CPU and 2B/Vulkan.
Each real installer publishes the seeded model, verifies its runtime and reuses
the installation on a second call with zero HTTP requests. Native inference
produces three complete samples, restores the prefix and independently observes
all inventory/inference exits. This proves cached setup/inference, not general
tier latency. Original reports/digests are retained under
`eval/hardware/results/2026-11-12-cleanup-setup/`. UI integration remains next.

## Settings controls

Settings → Models now shows the measured recommendation, a cleanup model choice,
CPU/GPU processor choice, combined transfer size, both licenses and source credits.
Fresh unused defaults can prefill the recommendation; existing custom paths and
processors remain selected. Refreshing performance updates guidance and does not
replace the user's selection. Lite/pending recommendations preselect no model.

Download / Resume explicitly installs or verifies the selected package on the
background download worker. Progress and Pause are independent of the speech
download. A successful model setup fills the GGUF path without enabling cleanup
or applying Settings. The user enables cleanup and presses Apply. Failed/paused
work keeps the previous path, and closing Settings requests pause. The existing
worker-lifetime guard retains the signal source until physical worker exit.

Custom GGUF paths can install processor files alone, with their size/licenses
shown and no catalog weights fetched. The old unpinned Qwen2.5 link is removed.
The Models page scrolls at the existing 760×560 minimum so all controls remain
reachable. The isolated Settings replay uses the real cached installer, forbids
HTTP, checks configuration before/after Apply and renders both viewport positions.
It changes no owner profile, microphone, hooks, History or insertion.

Settings validation: 1505 tests pass with four optional native skips; rules
432/432, authored adversarial checks 100/100 and Ruff/diff checks pass. The
initial real cached replay passes with zero HTTP, an unchanged configuration
until Apply, explicit enablement and unchanged speech preferences. Both Models
viewport positions were rendered and reviewed at 760×560. Immutable-source
Settings proof follows separately; broader gated tier acceptance remains open.
