# Voice Coding and Dictation for Developers | Saydraft

Canonical: https://tanzir71.github.io/saydraft/dictation-for-developers/

Use local Windows dictation for coding prompts, notes and commit messages. Learn Saydraft's Code mode, dictionary, shortcuts and review limits.

Facts checked: 2026-11-14

Voice typing is useful for the prose around development: a prompt for a coding assistant, a bug report, a design note or a commit-message draft. Saydraft runs speech models locally on Windows and lets you review the resulting text.

 

Use it in a supported editable field in VS Code, Cursor, a browser or another editor. There is no dedicated Cursor, Claude Code or Codex integration. Test the actual field and privilege level you use before relying on automatic delivery.

 

## Choose processing that fits the text

 

Use Code mode when prose rewriting could damage literal material. Raw mode is another option for retaining recognized wording. Neither mode turns the speech recognizer into a syntax-aware programming tool: identifiers, paths, symbols and shell commands still need review.

 

For a natural-language issue or email, a Style can choose a different tone and cleanup intensity. Keep technical terms in the dictionary, and use snippets for known text you deliberately want to insert.

 

## A practical first workflow

 

- Complete [local model setup](https://tanzir71.github.io/saydraft/docs/getting-started/).
 
- Start in a scratch document, then try your real editor’s input field.
 
- Dictate a short plain-language prompt and check names, negation and numbers.
 
- Copy the reviewed result when a field cannot support safe automatic insertion.

 

Avoid treating spoken terminal text as permission to execute it. Review an instruction before pressing Enter yourself. Optional spoken-Enter behavior is separate and off by default.

 

## Experimental editing tools

 

Pro/Labs Command Mode can edit selected text with a separately installed local model. Ask can explain selected text in a separate answer note. These features have bounded selection and output checks, but those checks do not prove that every answer or edit preserves meaning.

 

Saydraft has an [unsigned Windows portable preview](https://tanzir71.github.io/saydraft/download/) and source setup. Broader native workflow qualification, language accuracy and release latency remain in progress. The [offline guide](https://tanzir71.github.io/saydraft/offline-dictation-windows/) explains model and privacy trade-offs before you choose a daily workflow.

## A few useful answers.

### Can I use Saydraft with VS Code, Cursor or a coding assistant?

Saydraft can deliver text to supported editable Windows fields. Try the exact editor or terminal field you use; it has no dedicated integration with those products, and field or privilege restrictions can require Copy recovery.

### Will Code mode turn speech into correct program syntax?

Code mode avoids ordinary prose cleanup. It is not a programming-language parser and cannot guarantee correct identifiers, punctuation, commands or generated code. Review the result before running it.

## Sources and further reading

- [Saydraft styles and Code mode ↗](https://github.com/tanzir71/saydraft/blob/main/docs/STYLES.md)

- [Source setup and current qualification ↗](https://github.com/tanzir71/saydraft)

- [Experimental Command Mode ↗](https://github.com/tanzir71/saydraft/blob/main/docs/COMMAND_MODE.md)
