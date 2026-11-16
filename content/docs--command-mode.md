# Saydraft Command Mode — Edit Selected Text Locally

Canonical: https://tanzir71.github.io/saydraft/docs/command-mode/

Set up experimental Saydraft Command Mode, hold a shortcut to edit selected text, cancel with Escape and recover validated results with Copy.

Facts checked: 2026-11-14

Command Mode is experimental and off by default. Full physical shortcut and packaged interaction acceptance remain in progress.

 

## Review the local editing setup

 

Use the Pro hardware/performance profile. In Settings → Labs → Command and Translate, review the editing model/runtime, sizes, sources and licenses. Choose Download / Resume editing model, then enable Command Mode and Save.

 

Downloading starts no recording and does not enable the feature. The editing model is separate from ordinary speech and cleanup settings. Standard shows Needs Pro tier before Command target/model/microphone work.

 

## Select, hold and instruct

 

- Select the complete text you want to edit.
 
- Hold Ctrl + Win + Alt and wait for the Command label before speaking.
 
- Say a short instruction such as “make this shorter”, “make this more formal” or “turn this into bullets”.
 
- Release the shortcut to edit. Escape cancels.

 

The model works locally on the reviewed selection and instruction. A validated complete result can replace the original selection after target checks. It can still be imperfect; review wording and meaning before using it elsewhere.

 

## When the app cannot expose a selection

 

Allow clipboard-copy fallback is a separate, default-off Labs setting. Enable and save it only if you want that route. Keep your text selected, record the instruction and release all shortcut modifiers. The fallback uses ordinary Ctrl+C in the original known-safe field and restores the current clipboard.

 

Windows and target-app clipboard history or sync can retain that copy. Restoring the current clipboard cannot retract those entries. Read [the clipboard privacy boundary](https://tanzir71.github.io/saydraft/privacy/) before enabling fallback.

 

## Copy and recovery

 

When the original selection cannot be verified for replacement, a validated result is offered for Copy. A changed, unknown or password field can refuse the operation. History records the instruction and available result locally; an unsuccessful generation or validation can preserve the heard instruction for review. Command rows do not use ordinary dictation paste-last or audio retry.

 

## Related local features

 

Translate while speaking uses an independent Labs choice and Style output target. Ask about a selection produces a separate local answer rather than replacing source text. The shared editing download does not enable either feature. See [Style and spoken translation](https://tanzir71.github.io/saydraft/docs/styles/) and the [Ask implementation guide](https://github.com/tanzir71/saydraft/blob/main/docs/ASK.md).

## A few useful answers.

### Does downloading the editing model enable Command Mode?

No. Downloading, enabling Command Mode and enabling its clipboard fallback are separate actions. Command is off by default and also requires the Pro profile.

### Why did I get Copy instead of automatic replacement?

The app offers a validated result for Copy when it cannot verify the original selection for replacement. Changed or protected targets can prevent delivery.

## Sources and further reading

- [Command setup, editing and current qualification ↗](https://github.com/tanzir71/saydraft/blob/main/docs/COMMAND_MODE.md)

- [Separate clipboard-copy fallback and its boundaries ↗](https://github.com/tanzir71/saydraft/blob/main/docs/COMMAND_CLIPBOARD.md)
