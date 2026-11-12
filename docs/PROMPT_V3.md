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
quality evidence. App adapter integration still follows; the running app uses
its existing cleanup path at this foundation stage.

Validation: 601 tests pass, four optional native skips with real preview/Silero/LID
enabled; cleanup evaluation 42/42; Ruff and diff checks pass.
