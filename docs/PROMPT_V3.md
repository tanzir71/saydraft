# Cleanup prompt v3

`cleanup/llm/prompts` defines the plain-text contract: clean the transcript,
preserve meaning/language/details and never answer, translate or execute its
content. Questions and requests intended for another app stay questions and
requests. Profanity remains uncensored. The system also forbids JSON wrappers,
role labels, explanations and thinking text.

Each selected style has eight user/assistant demonstrations. They include a
dictated factual question, a request for a poem, an instruction-injection phrase,
meaningful “actually”, an explicit correction, protected details and profanity.
Neutral/formal/casual/very-casual examples are separate from the final dictation;
there is one system role. This is a prompt contract, not proof of model accuracy
or resistance to every injection. The validator and model bake-off remain needed.

The final user message has the specified app/group/style/intensity/language
header, at most forty glossary entries and the complete XML-escaped transcript.
App names and terms are bounded to 120 characters; caret context uses its last
120 characters. Metadata/glossary angles and controls are JSON escaped so they
cannot create structural transcript boundaries. The builder never truncates the
dictation to meet a budget: the client can decline inference and keep rules.

The protected-token bridge maps existing glossary/span placeholders and literal
token-looking text into collision-free `⟦Tn⟧` tokens for the model. Restoration
requires their exact occurrence count and order, and rejects missing, invented
or malformed tokens. It then restores the existing pipeline placeholders, keeping
legacy rule/restore behavior compatible. The output ceiling is
`ceil(1.25 × input_tokens) + 16`; streaming inference must also enforce its
configured cap, completion status and deadline before accepting any text.

Both build entry points collect the two text/JSON prompt resources through
PyInstaller's package-data helper. Actual collection finds both files. Contract
tests cover all styles, untrusted markup/metadata, Unicode, glossary/context
bounds, full-word preservation, token collisions/order/counts and isolation of
mutable message lists.

`CleanupClient` now tokenizes the complete protected transcript, then consumes
the server's UTF-8 SSE chat response within one manager lease and absolute
deadline. It requests deterministic plain text with thinking disabled, the
configured output cap and `</out>` stop. The decoder handles fragmented Unicode,
CR/LF boundaries, comments and multiline data with bounded line/event/body sizes.
It does not publish partial text or accumulate reasoning fields. Only a finished
`stop` response followed by `[DONE]`, with no tool calls and exact protected-token
restoration, can become a candidate. Length limits, malformed events, missing
completion markers, timeouts and token changes return fallback metadata.

The fake-model contract verifies that there is no JSON response-format request
or output JSON decoding. A real owned CPU server also passes SSE decoding under
NetworkGuard; the eight-token developer probe stops with `length`, which the
cleanup client deliberately refuses. This is transport evidence, not model
quality evidence.

The app's `LocalLLMCleaner` now delegates to this owned streaming path. The
legacy Python `llama_cpp` import and JSON output prompt/parser are removed.
Captured app/group, detected language, last caret context and glossary feed the
prompt; raw/code dictation bypasses cleanup requests. Complete candidates still
pass the pipeline validator before glossary/span restoration, History and
insertion. History records acceptance or fallback metadata. The existing
`clean(text, tone_hint=...)` interface remains compatible with injected cleaners.

Worker startup/arming warms only enabled, installed cleanup files in the
background. Missing/unready files preserve rules immediately; settings replacement
closes the previous cleaner before warming its successor. Shutdown stops cleanup
and refuses late candidates. CPU is the default backend; `llm.backend` explicitly
selects CPU/Vulkan, `timeout_ms` defaults to 800 and `idle_seconds` to 900. Context
defaults to 4096. Legacy temperature/top-p/GPU-layer preferences remain readable
but decoding uses temperature zero and the selected runtime's GPU policy.

A complete safe fake-model response passes through the real streaming adapter,
validator, SQLite History and insertion stub. Changed numbers, lost protected
tokens and partial output instead retain the rules text. The native app probe
also passes 100 capture/process/History/stub-insertion cycles, including forced
termination and deadline fallback; all fifty cleanup processes exit on shutdown.
It uses a checksum-restricted developer-only context override because the tiny
fixture declares only 128 tokens, below this prompt's 1277-token test request.
The model file is unchanged and supplies no cleanup-quality result. The original
context-overflow run and an overly strict probe-classifier failure remain in QA.

Validation: 624 tests pass, four optional native skips with real preview/Silero/LID
enabled; cleanup evaluation 42/42; Ruff and diff checks pass.
