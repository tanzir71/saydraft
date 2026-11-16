# Saydraft Dictionary — Names, Replacements and Learning

Canonical: https://tanzir71.github.io/saydraft/docs/dictionary/

Add names and protected terms to Saydraft, use explicit replacements, preview edits, and choose optional local correction suggestions and Undo.

Facts checked: 2026-11-14

## Add the spelling you want

 

Open Hub → Dictionary to add people, places and specialist terms. Protected terms help retain exact wording through cleanup. Use an explicit replacement pair when a particular recognized phrase should become another phrase, rather than expecting a fuzzy match to infer your intention.

 

Dictionary, replacement and protected-term edits are staged until Save. The [Style preview](https://tanzir71.github.io/saydraft/docs/styles/) includes those pending edits without writing them to disk. Fix an invalid draft before saving.

 

## Understand spelling correction

 

Normal resolved English dictation can use conservative phonetic and spelling evidence to correct close matches to dictionary names, without another ASR pass. Ambiguous targets, common words, numbers, code, identifiers and protected/literal text decline fuzzy changes. Explicit replacement pairs take priority.

 

Raw, Verbatim-ish, Code, translation, unknown or other languages and mixed scripts do not receive these English phonetic guesses. Longer unsupported entries retain their exact protection rather than being silently shortened. History retains the original recognized text alongside the processed result.

 

The public evaluation covers a limited English name set; it does not establish general or owner accuracy. See the linked investigation for its method and limits.

 

## Choose correction suggestions

 

Suggest words from corrections is experimental and off by default. When enabled, local observation of the original editable field can identify a narrow word correction after a dictation. The suggestion offers Add or Dismiss. It does not enable a cloud learning service.

 

Auto-add to dictionary is a separate, default-off choice available with suggestions. It saves eligible additions automatically and offers Undo after a successful save. Keep Auto-add off if you prefer to approve suggestions yourself. Native/manual behavior is still being qualified.

 

## Undo and conflicting edits

 

Undo belongs to that saved addition. It preserves unrelated dictionary changes and can decline when a newer/manual change has claimed the same term. It does not undo the words you edited in another app.

 

An edited stale dictionary draft is refused before shared settings are saved. Keep your draft, then use Reload Dictionary to review the latest saved version before trying again. Invalid data are not replaced with an empty dictionary.

 

## Keep the privacy boundary clear

 

Suggestions involve optional local field observation. Audio retention and Command Mode’s clipboard fallback are separate settings. Read [privacy](https://tanzir71.github.io/saydraft/privacy/) for those boundaries, and use [troubleshooting](https://tanzir71.github.io/saydraft/docs/troubleshooting/) if saving or recognition behaves unexpectedly.

## A few useful answers.

### Does the dictionary guarantee correct recognition?

No. It can protect terms and support conservative spelling correction, but it does not retrain the speech model or establish accuracy for every word or language. Review the result.

### Will learning add words without asking?

Correction suggestions are off by default. Auto-add is a separate default-off choice; with it off, use Add or Dismiss for a suggestion. A successfully saved addition can offer Undo.

## Sources and further reading

- [Dictionary storage, suggestions and Undo ↗](https://github.com/tanzir71/saydraft/blob/main/docs/DICTIONARY_LEARNING.md)

- [Qualified correction scope and measured limits ↗](https://github.com/tanzir71/saydraft/blob/main/docs/spikes/biasing.md)
