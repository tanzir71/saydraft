"""Guarded file-only development comparison of a frozen 40-name glossary.

No app defaults, user dictionary, profile, correction rules or confirmation audio
are changed. All model and corpus directories must already exist explicitly.
"""

from __future__ import annotations

import argparse
from collections import Counter
import gc
import json
from pathlib import Path
import statistics
import subprocess
import time

from tools.dictionary_names_corpus import (
    ARMS, PAIRS, file_digest, load_corpus, protected_errors, term_counts, write_new,
)


def summarize(cases, plan):
    """Recompute scores and require the complete frozen identity/ordering."""
    from tools.bench_models import score

    selected = plan['cohorts']['development']
    expected_ids = [row['id'] for row in selected]
    complete = len(cases) == len(ARMS) * len(selected) and bool(selected)
    arms, by_arm = {}, {}
    for arm in ARMS:
        rows = [row for row in cases if row.get('arm') == arm]
        totals, terms, protections = Counter(), Counter(), Counter()
        identities = [row.get('id') for row in rows]
        valid = identities == expected_ids and len(set(identities)) == len(identities)
        for row, expected in zip(rows, selected):
            if (row.get('reference') != expected['reference'] or row.get('error') is not None
                    or row.get('source_filename') != expected['source_filename']
                    or row.get('role') != expected['role']):
                valid = False
            totals.update(score(expected['reference'], row['text']))
            terms.update(term_counts(expected['reference'], row['text'], plan['terms']))
            protections.update(protected_errors(expected['reference'], row['text'], plan['terms']))
        complete = complete and valid
        by_arm[arm] = rows
        arms[arm] = {'cases': len(rows), 'failures': sum(row.get('error') is not None for row in rows),
                     'scores': dict(totals), 'terms': dict(terms), 'protected_errors': dict(protections),
                     'term_recall': terms['matched'] / terms['expected'] if terms['expected'] else None,
                     'decode_p50_seconds': statistics.median(row['seconds'] for row in rows) if rows else None}
    comparisons = {}
    for candidate, baseline in PAIRS.items():
        old, new = arms[baseline], arms[candidate]
        gain = new['term_recall'] / old['term_recall'] - 1 if old['term_recall'] and new['term_recall'] is not None else None
        regressions = []
        for original, proposed, reference in zip(by_arm[baseline], by_arm[candidate], selected):
            before = score(reference['reference'], original['text'])
            after = score(reference['reference'], proposed['text'])
            before_protected = protected_errors(reference['reference'], original['text'], plan['terms'])
            after_protected = protected_errors(reference['reference'], proposed['text'], plan['terms'])
            failed = [key for key in ('word_errors', 'character_errors') if after[key] > before[key]]
            failed += [key for key in before_protected if after_protected[key] > before_protected[key]]
            if (term_counts(reference['reference'], proposed['text'], plan['terms'])['false_positives'] >
                    term_counts(reference['reference'], original['text'], plan['terms'])['false_positives']):
                failed.append('term_false_positives')
            if failed:
                regressions.append({'id': reference['id'], 'role': reference['role'], 'metrics': failed})
        passed = bool(complete and gain is not None and gain >= plan['gate']['relative_term_recall_gain_min']
                      and new['terms']['false_positives'] <= old['terms']['false_positives'] and not regressions)
        comparisons[candidate] = {'baseline': baseline, 'relative_term_recall_gain': gain,
                                  'per_clip_regressions': regressions,
                                  'added_term_false_positives': new['terms'].get('false_positives', 0) - old['terms'].get('false_positives', 0),
                                  'development_gate_passed': passed}
    return {'complete': complete, 'expected_cases': len(selected) * len(ARMS), 'completed_cases': len(cases),
            'arms': arms, 'comparisons': comparisons,
            'development_gate_passed': any(row['development_gate_passed'] for row in comparisons.values()),
            'confirmation_inferred': False, 'ship_or_owner_acceptance': False}


def evaluate(corpus_path, parakeet_dir, whisper_dir, tokenizer_dir, output):
    import numpy as np
    import soundfile as sf
    from saydraft.models.downloader import installation_ready
    from saydraft.models.manifest import get_model
    from saydraft.privacy.netguard import NetworkGuard
    from saydraft.privacy.telemetry import disable_sherpa_telemetry
    from tools.bench_models import score

    corpus_path = Path(corpus_path)
    parakeet_dir, whisper_dir, tokenizer_dir, output = map(Path, (parakeet_dir, whisper_dir, tokenizer_dir, output))
    plan, cohorts = load_corpus(corpus_path)
    clips = cohorts['development']  # Reserved files are hash-validated, never decoded.
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    if subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip():
        raise ValueError('Commit the comparison source before inference')
    corpus_hash = file_digest(corpus_path)
    plan_hash = file_digest(corpus_path.parent / 'plan.json')
    directories = {'parakeet-tdt-0-6b-v3-int8': parakeet_dir, 'whisper-large-v3-turbo': whisper_dir}
    fingerprints = {}
    for model_id, directory in directories.items():
        model = get_model(model_id)
        if not installation_ready(model, directory, check_hashes=True):
            raise ValueError('Explicit pinned model files are missing or changed')
        fingerprints[model_id] = {row['path']: file_digest(directory / row['path']) for row in model['files']}
    tokenizer = json.loads((tokenizer_dir / 'receipt.json').read_bytes())
    if (tokenizer.get('all_token_ids_match') is not True or tokenizer.get('pieces') != 8192
            or tokenizer.get('tokens_sha256') != file_digest(parakeet_dir / 'tokens.txt')
            or tokenizer.get('vocab_sha256') != file_digest(tokenizer_dir / 'tokenizer.vocab')
            or tokenizer.get('tokenizer_sha256') != file_digest(tokenizer_dir / 'tokenizer.model')):
        raise ValueError('Authentic tokenizer receipt or bytes changed')
    output.mkdir(parents=True, exist_ok=False)
    (output / 'plan.json').write_bytes((corpus_path.parent / 'plan.json').read_bytes())
    write_new(output / 'started.json', {'source': source, 'source_clean': True, 'corpus_sha256': corpus_hash,
                                       'plan_sha256': plan_hash, 'expected_cases': len(clips) * len(ARMS),
                                       'models': fingerprints, 'complete': False})
    rows, loads, runtimes = [], {}, {}
    NetworkGuard.install()
    try:
        import sherpa_onnx
        import faster_whisper

        runtimes = {'sherpa_onnx': sherpa_onnx.__version__, 'faster_whisper': faster_whisper.__version__}
        if runtimes != {'sherpa_onnx': '1.13.4', 'faster_whisper': '1.2.1'}:
            raise ValueError('Use the frozen native runtime versions')
        disable_sherpa_telemetry(sherpa_onnx)
        parameters = plan['parameters']
        whisper = None
        with (output / 'cases.jsonl').open('x', encoding='utf-8', newline='\n') as journal:
            for arm in ARMS:
                started = time.perf_counter()
                if arm.startswith('parakeet_'):
                    engine = sherpa_onnx.OfflineRecognizer.from_transducer(
                        encoder=str(parakeet_dir / 'encoder.int8.onnx'), decoder=str(parakeet_dir / 'decoder.int8.onnx'),
                        joiner=str(parakeet_dir / 'joiner.int8.onnx'), tokens=str(parakeet_dir / 'tokens.txt'),
                        model_type='nemo_transducer', num_threads=parameters['threads'], provider='cpu',
                        decoding_method='greedy_search' if arm == 'parakeet_greedy' else 'modified_beam_search',
                        max_active_paths=parameters['parakeet_max_active_paths'],
                        hotwords_score=parameters['parakeet_hotwords_score'], modeling_unit='bpe',
                        bpe_vocab=str(tokenizer_dir / 'tokenizer.vocab'))
                elif whisper is None:
                    whisper = faster_whisper.WhisperModel(str(whisper_dir), device='cpu', compute_type='int8',
                                                         cpu_threads=parameters['threads'], num_workers=1,
                                                         local_files_only=True)
                    context_tokens = whisper.hf_tokenizer.encode(' ' + parameters['whisper_context']).ids
                    if len(context_tokens) >= whisper.max_length // 2:
                        raise ValueError('Frozen glossary exceeds the native context token limit')
                    runtimes['whisper_context_tokens'] = len(context_tokens)
                loads[arm] = time.perf_counter() - started
                for index, clip in enumerate(clips):
                    audio, rate = sf.read(clip['audio_path'], dtype='float32', always_2d=False)
                    if rate != 16000 or audio.ndim != 1 or len(audio) != clip['num_samples'] or not np.isfinite(audio).all():
                        raise ValueError('Audio does not match its frozen 16 kHz mono reference')
                    text, error, started = '', None, time.perf_counter()
                    try:
                        if arm.startswith('parakeet_'):
                            stream = engine.create_stream(' / '.join(plan['terms'])) if arm == 'parakeet_hotwords' else engine.create_stream()
                            stream.accept_waveform(16000, audio)
                            engine.decode_stream(stream)
                            text = stream.result.text
                            del stream
                        else:
                            segments, _info = whisper.transcribe(
                                audio, language=parameters['whisper_language'], beam_size=parameters['whisper_beam_size'],
                                vad_filter=parameters['whisper_vad_filter'],
                                condition_on_previous_text=parameters['whisper_condition_on_previous_text'],
                                hotwords=parameters['whisper_context'] if arm == 'whisper_context' else None)
                            text = ''.join(segment.text for segment in segments).strip()
                        if type(text) is not str:
                            raise TypeError('Native recognizer returned a non-string transcript')
                    except Exception as exc:
                        text, error = '', type(exc).__name__
                    row = {'arm': arm, 'id': clip['id'], 'source_filename': clip['source_filename'],
                           'audio_sha256': clip['sha256'], 'reference': clip['reference'], 'role': clip['role'],
                           'text': text, 'error': error, 'seconds': time.perf_counter() - started,
                           'terms': term_counts(clip['reference'], text, plan['terms']),
                           'scores': score(clip['reference'], text),
                           'protected_errors': protected_errors(clip['reference'], text, plan['terms'])}
                    rows.append(row)
                    journal.write(json.dumps(row, ensure_ascii=False) + '\n')
                    journal.flush()
                    if (index + 1) % 10 == 0 or index + 1 == len(clips):
                        print(json.dumps({'arm': arm, 'completed': index + 1, 'expected': len(clips)}), flush=True)
                if arm.startswith('parakeet_'):
                    del engine
                    gc.collect()
        del whisper
        gc.collect()
        result = {**summarize(rows, plan), 'source': source, 'source_clean': True,
                  'corpus_sha256': corpus_hash, 'plan_sha256': plan_hash, 'model_files': fingerprints,
                  'model_files_unchanged': all(file_digest(directories[model_id] / name) == value
                                               for model_id, files in fingerprints.items() for name, value in files.items()),
                  'corpus_unchanged': file_digest(corpus_path) == corpus_hash,
                  'plan_unchanged': file_digest(corpus_path.parent / 'plan.json') == plan_hash,
                  'tokenizer_receipt_sha256': file_digest(tokenizer_dir / 'receipt.json'),
                  'runtimes': runtimes, 'model_load_seconds': loads, 'silence_trim': False,
                  'python_network_guard': NetworkGuard.is_installed(), 'native_firewall_verified': False,
                  'scope': 'public_English_read_speech_development_shared_prompts_reserved_recordings_uninferred',
                  'release_latency_or_broad_accuracy_accepted': False}
        write_new(output / 'report.json', result)
        return result
    finally:
        NetworkGuard.uninstall()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--parakeet-dir', type=Path, required=True)
    parser.add_argument('--whisper-dir', type=Path, required=True)
    parser.add_argument('--tokenizer-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    result = evaluate(args.corpus, args.parakeet_dir, args.whisper_dir, args.tokenizer_dir, args.output)
    print(json.dumps({key: result[key] for key in ('complete', 'development_gate_passed', 'confirmation_inferred', 'ship_or_owner_acceptance')}))


if __name__ == '__main__':
    main()
