# Translate while speaking · Labs

Translate uses your normal dictation shortcut and a saved output language for
each app group. It translates recognized speech locally; it does not translate
the selected document text. This experimental Pro feature is off by default.

1. In Settings → Models, select Pro or use a saved performance recommendation
   that admits Pro. A manual tier override is not a speed measurement.
2. In Settings → Labs → **Command and Translate · experimental**, review the
   model, runtime, sizes and licenses. Choose **Download / Resume editing model**.
   Command and Translate share the pinned Qwen3.5 4B model and selected CPU or
   Vulkan runtime. An existing verified installation is reused.
3. Enable **Translate while speaking** and Save. Command has a separate toggle;
   neither feature requires enabling the other.
4. In Style → **Translate while speaking · Labs**, choose an app group and a
   spoken output language: English, Spanish or Arabic. Save your settings.
   **Keep recognized language** removes that group's translation target.
5. Focus the intended field, hold your usual dictation shortcut, wait for the
   **Translate** label, then speak and release. Model preparation can take time
   before listening starts. Esc cancels. Translation is generated after release.

Selecting a target or enabling Labs downloads nothing. Missing model files refuse
before microphone capture and direct you back to Labs. Later launches reuse the
installed files. The shared ASR All languages model is separately needed to
recognize Arabic or Bengali; it is not a language pack for the translation model.
See [models and languages](MODELS.md) and [ASR routing](ASR_ROUTING.md).

Raw mode, Code profiles and the Code app group bypass translation. Other groups
without a target keep ordinary dictation. A recording snapshots its group,
target, services and settings; saving a change does not retarget an active task.
Normal cleanup model choices and default shortcuts stay as configured.

## Results and recovery

Translation bypasses ordinary cleanup, snippets, correction learning and voice
Enter. The editor receives recognized speech and a fixed translation instruction,
without the target field's selected text or words before the caret. Default
recognition can still process completed speech segments during capture. Optional
English live preview stays visual: its words never replace final recognition for
automatic translation, even when the separate streaming-result option is on.
Incomplete recognition or recovered preview words are saved for review instead.

Successful output is saved to History before normal guarded delivery. If focus,
field safety or delivery checks fail, an independent **Translation** recovery
window offers Copy and local autosave. A rejected, incomplete, timed-out or
unavailable translation keeps the recognized speech in History and an independent
**Recognized speech** recovery window; untranslated words are not pasted
automatically. If History itself fails, both distinct versions are preserved in
session recovery and separate local notes where available. These windows do not
copy automatically.

History shows source and target language, speech/editing model, outcome and
timings. Successful translations support Copy/Paste translation and paste-last.
Failed translation rows offer Copy recognized speech and are excluded from
paste-last. Ordinary audio retry is disabled for both kinds of translation row;
start a new Translate dictation. Audio retention follows your saved preference
and remains off by default.

## Validation and qualification

Translation allows language changes that ordinary cleanup refuses. Existing
bounded edit validation still protects numbers, URLs, emails, code literals,
placeholders and currency symbols. The translation wrapper also checks numeric
times/dates, currency codes and amount associations. Literal code is replaced by
fresh opaque slots for generation, checked, then restored in one pass. Missing
or altered slots refuse delivery. A full completed reply is required; output is
never cut to fit. Requests use the existing 8,192 UTF-16-unit input and 16,384-unit
output limits and a 45-second generation timeout.

The target-script check distinguishes Arabic from Latin script; it is not a
complete language detector or semantic correctness proof. Fluent wrong wording,
negation or names can still require review. Native smoke cases cover English↔Spanish
and English↔Arabic, protected details, and instructions translated as text rather
than executed. They do not establish broad translation quality, speech accuracy,
end-to-end physical hotkey/microphone/paste acceptance or release latency.

The [verification record](../eval/translation/results/2026-11-14-spoken/README.md)
keeps controlled worker tests, native text-generation checks and offscreen UI
renders separate, including the initial diagnostic failures and their fixes.

For a developer-owned verified cache, this probe makes no downloads and opens no
microphone or target application:

```powershell
python -m tools.probe_translation --models-dir D:\QA\VerifiedAppCache --backend vulkan --device Vulkan1 --output D:\QA\Translate-New
```

The backend setting is shared with Command. Recommended uses the saved hardware
report even when Pro is selected manually; setup and capture resolve the same
runtime. The exclusive editor retires ordinary cleanup's owner, and cancellation
or completion revokes this task's generation before a later task can deliver.
