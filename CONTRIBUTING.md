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
checks below when you only need to validate code. Do not use the legacy
`tools/build.ps1` for release builds while its clean-environment rewrite is
pending. Installer and clean-machine acceptance are tracked under P8.

## App checks

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
[Windows CI workflow](.github/workflows/ci.yml) documents its pinned VAD fixture
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
setup preferences. The current wizard does not gate Finish on installed weights.
Practice does gate completion on observed retirement of its microphone and
temporary shortcuts; these are separate checks.

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
and remaining benchmark/readiness work.

### Reports and licensing

Link to dated measurements rather than
rewriting historical results as current acceptance. Describe a reproducible
failure with the source commit, Windows/Python version, relevant configuration,
and redacted logs in a [GitHub issue](https://github.com/tanzir71/saydraft/issues).
Do not attach private transcripts, recordings, databases, credentials, or
unredacted debug logs.

The project's own code is [MIT licensed](LICENSE). Downloaded weights, fonts,
data, and dependencies keep their [separate licenses](THIRD_PARTY_NOTICES.md).
