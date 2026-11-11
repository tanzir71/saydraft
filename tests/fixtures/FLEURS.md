# FLEURS smoke fixtures

These two speech recordings and their reference transcripts come from
[Google FLEURS](https://huggingface.co/datasets/google/fleurs), by the FLEURS
contributors, licensed under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).
That license applies to these fixtures separately from Saydraft's MIT license.

- `fleurs-bn.wav`: Bengali (`bn_in`), validation/dev split, utterance 1570,
  original filename `11351836784838042299.wav`. Downloaded from the published
  [Google archive](https://storage.googleapis.com/xtreme_translations/FLEURS102/bn_in.tar.gz),
  using `bn_in/dev.tsv` for the independent reference transcript.
- `fleurs-ar.wav`: Arabic (`ar_eg`), test split, row 0, utterance 1993.
  Downloaded from the [dataset viewer](https://huggingface.co/datasets/google/fleurs/viewer/ar_eg/test?row=0).

Audio bytes are unchanged; files were renamed locally. Their JSON sidecars retain
source filenames, dataset revision, reference text, license and SHA-256 hashes.
These are deterministic script-output smoke samples, not an accuracy corpus or
evidence of owner-clip performance. Owner accuracy acceptance is deferred by request.
