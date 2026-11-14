# Dictionary biasing: rejected development candidate

Clean native source: `209bc3727ddd6bab18c2339bd4c231313a4f9378`.
Forty reference-selected terms, 20 previously evaluated public FLEURS English
clips, three Parakeet decoder arms, 60 complete decodes. This is development
reuse, not an unseen glossary, owner accuracy or broad language acceptance.

| Arm | Matched / expected terms | Word errors | Character errors |
|---|---:|---:|---:|
| Greedy | 36/42 | 55 | 198 |
| Beam | 37/42 | 58 | 208 |
| Beam with hotwords | 36/42 | 63 | 214 |

The original ≥30% relative recall gate fails: dictionary gain is zero and errors
increase. No defaults or post-correction change. At baseline recall 85.71%, even
perfect recognition could gain only 16.67% on these ordinary long words. A harder
reference-only name/glossary set and disjoint recordings are still needed. Do not
retune the observed selection, score or acceptance criteria.

The original plan, native text, per-case scores, public TSV/corpus, parent exit 0,
empty encoding-error log, SDK/profile guard and raw source bytes are retained.
Independent verification recomputes all 60 word/character distances and dictionary
counts from the raw hypotheses, checks every ID/reference/denominator, source
Git blobs, model catalog pins and original criteria. Optional roots rehash the
actual public audio, tokenizer and complete installed model files.

The tokenizer helper retrieves 370,649 bytes by bounded HTTP ranges from the
pinned NVIDIA NeMo archive, skips its weights, matches all 8,192 token IDs and
exports authentic float32 scores. The publisher's full archive checksum is
recorded but **not verified by partial ranges**. Tokenizer binaries/vocabulary,
model weights and audio remain in explicit local QA directories. This is not a
shipping tokenizer package or automatic download path. Attribution is retained
in `NOTICE.md` (Google FLEURS, CC-BY-4.0) and `tokenizer-NOTICE.md` (NVIDIA,
CC-BY-4.0). Original audio and tokenizer bytes are unchanged; vocabulary export
is a text representation of the original pieces/scores.

Forty-one focused local tests pass; the final expanded run passes 59, including
public-corpus acquisition and manual-only delivery contracts. The native process exits after 69 seconds
with unchanged source, plan and model hashes. Python NetworkGuard is active;
native firewall, microphone/loopback, foreground, clipboard and OS input are not
used or qualified. The unused 60-clip Bengali/Tamil/Telugu confirmation set is
untouched. No GitHub Actions run, PR, release or owner upload is needed.

```powershell
python eval/asr/results/2026-11-14-dictionary-biasing/verify-dictionary.py.txt --repo .
```

Add `--corpus-root PATH`, `--tokenizer-root PATH` and `--model-root PATH` to verify
the local payload bytes. The verifier uses only the standard library and never
imports an app, SDK or model. See [the investigation](../../../../docs/spikes/biasing.md).
