# Contributing to Saydraft

Saydraft is in active development. Read the [README](readme.md) for the current
setup and [documentation index](docs/README.md) for the area you want to change.
The [parity plan](WISPR_OFFLINE_PARITY_PLAN.md) tracks implemented work separately
from outstanding acceptance. Its historical entries are evidence, not a claim
that every feature is ready for release.

## Development environment

Use Windows and 64-bit Python 3.13. From the repository root, create an isolated
environment and install the development requirements:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
```

Run the app explicitly with `.venv\Scripts\python -m saydraft`. App launches
use your local profile and can install global shortcuts; use the offscreen
checks below when you only need to validate code. The rewritten
[packaging pipeline](docs/PACKAGING.md) creates a fresh build environment and
retains unsigned artifacts and audit reports. Its first clean build and disposable
installer lifecycle pass; signing and broader clean-machine acceptance remain under P8.

## App checks

Validate locally, commit and push directly. All GitHub Actions workflows are
manual-only; branch/tag pushes and pull requests start no checks or deployments.
Do not wait for an Actions result or dispatch a workflow as part of routine
delivery. Keep source-specific local receipts and distinguish fixture checks
from native hardware, physical-input and clean-machine acceptance.

These are the current lint, unit/offline, rules, and authored adversarial gates:

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
$env:HF_HUB_OFFLINE = '1'
$env:HF_HUB_DISABLE_TELEMETRY = '1'
$env:DO_NOT_TRACK = '1'
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m pytest tests -q -rs
.venv\Scripts\python -m saydraft.eval --min-pass-rate 100 --min-cases 556
.venv\Scripts\python -m saydraft.cleanup.llm.eval_validation --min-catch-rate 100 --min-cases 100
```

Native/model smoke tests may skip without explicit verified fixtures. The
[manual Windows workflow](.github/workflows/ci.yml) documents its pinned VAD fixture
bootstrap; additional optional fixtures and manual acceptance are described in
the [test checklist](docs/TEST_CHECKLIST.md). A skipped check is not acceptance.

Use temporary profiles, fixture databases, and disposable model directories.
Do not capture private speech, operate another person's clipboard/input devices,
or remove their model files as part of automated QA. Real microphone, shortcut,
focus, and insertion checks require a deliberate manual session. Keep generated
models, builds, environments, and reports out of version control.

When adding cleanup behavior, use representative regression cases and preserve
the evaluation contract. Do not relax deadlines, expected outputs, or
preservation checks to make a candidate pass. Distinguish deterministic rule
tests and authored validator cases from real ASR/LLM accuracy measurements.
See [evaluation](docs/EVALUATION.md) and [cleanup evidence](docs/CLEANUP_EVIDENCE.md).

The [soak guide](docs/SOAK.md) covers the canonical 200-cycle regression command
and its explicit native-cleanup recipe. Finish local checks and commit the source
before running a full native measurement from a clean checkout. Keep native runs
serial with other tests, builds and model transfers; use a fresh retained QA
directory. The runner uses memory clipboard/keyboard adapters, with physical
Windows acceptance tracked separately.

For post-rules AI cleanup changes, run the word-preservation, real-pipeline,
policy, and evidence checks as well:

```powershell
.venv\Scripts\python -m pytest tests/test_post_rules_words.py tests/test_cleanup_bakeoff.py tests/test_cleanup_gate.py tests/test_cleanup_policy_eval.py tests/test_cleanup_evidence.py -q -rs
```

Normal intensities 1–3 preserve content-word identity and order after rules,
with bounded grammar exceptions. Polished and the internal translation contract
have broader scope; Translate is not yet a user-facing feature. Keep these
contracts distinct and preserve the [validator's guarantees](docs/VALIDATOR_V2.md).
Native evidence must also fingerprint the pipeline that invokes validation.

Run native performance measurements serially from a clean, immutable checkout
with verified fixtures. Keep other model jobs, downloads, builds, and test suites
out of the measurement window. Record actual native process exit and preserve
original reports. Forced-generation quality, production-policy acceptance,
decoder throughput, and release-to-insertion latency are separate measurements;
rules fallback or a raw token rate cannot establish all four.

Use [the cold/warm matrix](docs/LATENCY_MATRIX.md) for the written 3/10/30/90-second
release-latency contract: `python -m tools.bench matrix --help`. It starts a fresh
process per cold/warm pair, checks History before simulated paste and retains
failed/partial evidence. Full recipes need twenty samples in each of eight cells,
a pinned VAD bundle, declared isolation and clean unchanged source. The legacy
`tools.bench --audio ...` command remains a scoped Whisper/rules smoke.

## Website and visual tokens

The public Astro site lives in `site/` and is published at
[GitHub Pages](https://tanzir71.github.io/saydraft/). Use Node 24.22.2 or newer:

```powershell
node tools/generate_tokens.mjs --check
cd site
npm ci
npm run build
npm run storybook:build
npx playwright install chromium --no-shell
npm test
```

The base path is `/saydraft/`. Edit `design/tokens.json` and regenerate with
`node tools/generate_tokens.mjs` from the repository root when changing shared
tokens. Do not hand-edit generated CSS/QSS. Browser snapshots run on Windows;
functional checks, Lighthouse setup, and deployment details are in
[the website guide](docs/SITE.md). The legacy root `index.html` and `demo/`
remain pending their planned archive/port; they are not the current Pages source.

## Documentation and reports

Keep setup instructions, defaults, download sizes, and licenses aligned with
the source and pinned model manifest. First-run capability recommendations are
provisional; they do not replace inference measurements or the saved performance
tier. Distinguish a completed file transfer, a verified model package, and saving
setup preferences. Next requires a verified package or a successfully loaded,
unchanged local Whisper model. Finish rechecks the current model asynchronously
before merging/saving preferences; Cancel/hide/navigation revoke late results.
Observed retirement of practice, shortcuts and performance work is a separate gate.

For user-facing setup changes, keep the [README](readme.md),
[first-run guide](docs/ONBOARDING.md), [documentation index](docs/README.md),
[project context](llms.txt), and public
[getting-started page](site/src/pages/docs/getting-started/index.astro) consistent.
Run `.venv\Scripts\python -m pytest tests/test_readme.py -q` to check the public
Markdown navigation. Changes under `site/` also need the website checks above;
successful Site checks trigger the Pages deployment for that exact commit.

### First-run setup checks

For changes to the connected setup flow, run its focused integration checks in
the offscreen environment above:

```powershell
.venv\Scripts\python -m pytest tests/test_practice.py tests/test_onboarding_practice.py tests/test_onboarding_window.py tests/test_onboarding_shortcuts.py tests/test_qt_app_shell.py tests/test_session_worker.py -q -rs
.venv\Scripts\python -m pytest tests/test_setup_benchmark.py tests/test_hardware_benchmark.py tests/test_setup_models.py -q -rs
.venv\Scripts\python -m pytest tests/test_onboarding_readiness.py tests/test_whisper_local.py tests/test_runtime_telemetry.py tests/test_microphone_privacy.py -q -rs
```

The six-page integration test uses synthetic native key packets, an injected
input stream, a mocked explicit download, private preferences, and queued Qt
signals. The optional recognizer case uses the public
[hello fixture](tests/fixtures/hello.wav) with an already installed, verified
Parakeet v3 model. To include that case, point to your disposable fixture model
directory; this command does not download weights:

```powershell
$env:SAYDRAFT_TEST_PARAKEET_V3_MODEL = 'D:\QA\models\parakeet-tdt-0-6b-v3-int8'
.venv\Scripts\python -m pytest tests/test_onboarding_practice.py -k synthetic_native_shortcut -q -rs
.venv\Scripts\python -m pytest tests/test_setup_benchmark.py -k selected_model_benchmark_through_worker -q -rs
```

Both cases use fake native hooks and input rather than operating the desktop,
microphone or clipboard. The optional case checks the real local recognizer and
cleanup path; it does not establish accuracy acceptance or physical shortcut
behavior. See the [first-run guide](docs/ONBOARDING.md) for ownership, cancellation
and remaining permission/manual acceptance.

For the optional real Whisper cache/readiness cases, provide an already verified
turbo model directory through `SAYDRAFT_TEST_WHISPER_TURBO_MODEL`. Keep pytest's
temporary folder on the same volume so disposable HF snapshots can link those
public fixtures without copying large weights. These tests never download a model.
They also verify cached-tokenizer reuse and missing-tokenizer rejection while
HTTP requests and account-token lookup are forbidden. Preserve any failed native
probe reports; an isolated success does not erase a broader failure.

### Scratchpad and Notes checks

Use the offscreen/offline environment above and disposable profile databases:

```powershell
.venv\Scripts\python -m pytest tests/test_notes.py tests/test_note_draft.py tests/test_scratchpad.py tests/test_notes_shortcuts.py tests/test_notes_shell.py tests/test_last_diff.py tests/test_data_migrations.py tests/test_config.py tests/test_hub.py tests/test_qt_app_shell.py -q -rs
```

These exercise real local SQLite saves, migration backups, stale revisions,
delayed writes, queued Qt acknowledgements, recoverable errors, synthetic native
actions, Notes search/reopen, last-diff selection, and flushing the latest draft
before Quit. They use fake clipboards and owned offscreen windows. Physical
Win/Alt/Ctrl key and Start-menu acceptance is a separate manual session. See the
[Notes guide](docs/NOTES.md).

### Reports and licensing

Link to dated measurements rather than
rewriting historical results as current acceptance. Describe a reproducible
failure with the source commit, Windows/Python version, relevant configuration,
and redacted logs in a [GitHub issue](https://github.com/tanzir71/saydraft/issues).
Do not attach private transcripts, recordings, databases, credentials, or
unredacted debug logs.

The project's own code is [MIT licensed](LICENSE). Downloaded weights, fonts,
data, and dependencies keep their [separate licenses](THIRD_PARTY_NOTICES.md).
