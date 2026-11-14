"""Explicit reserved-recording confirmation, admitted only after development."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import gc
import json
from pathlib import Path
import subprocess
import sys
import time

from tools.dictionary_correction import package_identity
from tools.dictionary_names_corpus import file_digest, load_corpus, protected_errors, sha256, term_counts, write_new

BASELINE = 'parakeet_greedy'
HINT = 'parakeet_hotwords'
ALLOWED = ('parakeet_greedy__phonetic', 'parakeet_greedy__context_then_phonetic')


def make_plan(development, corpus_path):
    development, corpus_path = Path(development).resolve(), Path(corpus_path).resolve()
    dev_plan = json.loads((development / 'plan.json').read_bytes())
    report = json.loads((development / 'report.json').read_bytes())
    passing = [arm for arm, value in report['comparisons'].items() if value['development_gate_passed']]
    if (not report['complete'] or not report['development_gate_passed'] or not passing
            or any(arm not in ALLOWED for arm in passing) or report['chosen_for_confirmation'] not in passing
            or report['confirmation_inferred'] or report['plan_sha256'] != file_digest(development / 'plan.json')):
        raise ValueError('Only independently verified passing Parakeet development candidates may advance')
    original, cohorts = load_corpus(corpus_path)
    if original['terms'] != dev_plan['terms'] or [row['id'] for row in cohorts['development']] != dev_plan['ids']:
        raise ValueError('Original development selection changed')
    repo = Path(__file__).resolve().parents[1]
    if set(dev_plan['algorithm_source_lf_sha256']) != {'saydraft/asr/biasing.py', 'tools/dictionary_correction.py'}:
        raise ValueError('Development algorithm fingerprints are incomplete')
    for name, value in dev_plan['algorithm_source_lf_sha256'].items():
        if sha256((repo / name).read_bytes().replace(b'\r\n', b'\n')) != value:
            raise ValueError('Do not retune the development candidate before confirmation')
    if package_identity() != dev_plan['package']:
        raise ValueError('Phonetic runtime bytes changed')
    if file_digest(repo / dev_plan['frequency']['file']) != dev_plan['frequency']['sha256']:
        raise ValueError('Do not retune the common-word list before confirmation')
    return {'schema': 1, 'protocol': 'dictionary_reserved_recordings_v1',
            'development': str(development),
            'development_files': {name: file_digest(development / name) for name in ('plan.json', 'report.json', 'cases.jsonl', 'verify-correction.py.txt')},
            'development_source': report['source'], 'corpus_path': str(corpus_path), 'corpus_sha256': file_digest(corpus_path),
            'terms': dev_plan['terms'], 'cohort': 'reserved_confirmation',
            'clips': [{key: row[key] for key in ('id', 'source_filename', 'sha256', 'reference', 'role')} for row in cohorts['reserved_confirmation']],
            'candidates': passing, 'arms': [BASELINE, HINT, *passing],
            'parameters': original['parameters'], 'gate': dev_plan['gate'],
            'algorithm_source_lf_sha256': dev_plan['algorithm_source_lf_sha256'],
            'confirmation_source_lf_sha256': sha256(Path(__file__).read_bytes().replace(b'\r\n', b'\n')),
            'package': dev_plan['package'], 'frequency': dev_plan['frequency'],
            'selection': 'Only the two development-passing candidates advance, unchanged. Decode the original lexically second reserved recordings; no case exclusion. They share reference prompts; speaker independence and unseen text are unverified.',
            'selection_policy': 'Among confirmation-passing candidates choose greatest name recall, then no additional hinted ASR decode, then lexical name. The development-selected combined candidate is included unchanged.',
            'owner_accuracy_accepted': False, 'ship_accepted': False}


def summarize(cases, plan):
    from tools.bench_models import score

    ids = [row['id'] for row in plan['clips']]
    arms, selected = {}, {}
    complete = bool(ids) and len(cases) == len(ids) * len(plan['arms'])
    for arm in plan['arms']:
        rows = [row for row in cases if row['arm'] == arm]
        complete = complete and [row['id'] for row in rows] == ids and len(set(row['id'] for row in rows)) == len(ids)
        terms, scores, surfaces = Counter(), Counter(), Counter()
        for row, expected in zip(rows, plan['clips']):
            complete = complete and row['error'] is None and all(row[key] == expected[key] for key in ('id', 'source_filename', 'reference', 'role'))
            complete = complete and row['audio_sha256'] == expected['sha256']
            terms.update(term_counts(expected['reference'], row['text'], plan['terms']))
            scores.update(score(expected['reference'], row['text']))
            surfaces.update(protected_errors(expected['reference'], row['text'], plan['terms']))
        arms[arm] = {'cases': len(rows), 'terms': dict(terms), 'scores': dict(scores), 'protected_errors': dict(surfaces),
                     'term_recall': terms['matched'] / terms['expected'] if terms['expected'] else None,
                     'edits': sum(len(stage['edits']) for row in rows for stage in row['stages'])}
        selected[arm] = rows
    comparisons = {}
    for arm in plan['candidates']:
        regressions = []
        for old, new in zip(selected[BASELINE], selected[arm]):
            before, after = score(old['reference'], old['text']), score(new['reference'], new['text'])
            previous = protected_errors(old['reference'], old['text'], plan['terms'])
            current = protected_errors(new['reference'], new['text'], plan['terms'])
            failed = [key for key in ('word_errors', 'character_errors') if after[key] > before[key]]
            failed += [key for key in previous if current[key] > previous[key]]
            if term_counts(new['reference'], new['text'], plan['terms'])['false_positives'] > term_counts(old['reference'], old['text'], plan['terms'])['false_positives']:
                failed.append('term_false_positives')
            if failed:
                regressions.append({'id': new['id'], 'role': new['role'], 'metrics': failed})
        before, after = arms[BASELINE]['term_recall'], arms[arm]['term_recall']
        gain = after / before - 1 if before and after is not None else None
        comparisons[arm] = {'relative_term_recall_gain': gain, 'regressions': regressions,
                            'confirmation_gate_passed': bool(complete and gain is not None and gain >= plan['gate']['relative_term_recall_gain_min']
                                and not regressions and arms[arm]['terms']['false_positives'] <= arms[BASELINE]['terms']['false_positives'])}
    passing = [arm for arm, value in comparisons.items() if value['confirmation_gate_passed']]
    chosen = sorted(passing, key=lambda arm: (-arms[arm]['term_recall'], arm != ALLOWED[0], arm))[0] if passing else None
    return {'complete': bool(complete), 'expected_cases': len(ids) * len(plan['arms']), 'completed_cases': len(cases),
            'arms': arms, 'comparisons': comparisons, 'confirmation_gate_passed': bool(passing),
            'chosen_candidate': chosen, 'owner_accuracy_accepted': False, 'ship_accepted': False}


def evaluate(plan_path, model_dir, tokenizer_dir, dependency_root, output):
    import numpy as np
    import soundfile as sf
    from saydraft.asr.biasing import DictionaryCorrector
    from saydraft.models.downloader import installation_ready
    from saydraft.models.manifest import get_model
    from saydraft.privacy.netguard import NetworkGuard
    from saydraft.privacy.telemetry import disable_sherpa_telemetry

    plan_path, model_dir, tokenizer_dir, dependency_root, output = map(Path, (plan_path, model_dir, tokenizer_dir, dependency_root, output))
    plan_bytes = plan_path.read_bytes()
    plan = json.loads(plan_bytes)
    if make_plan(plan['development'], plan['corpus_path']) != plan:
        raise ValueError('Frozen confirmation inputs, candidate, cohort or criteria changed')
    repo = Path(__file__).resolve().parents[1]
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo, text=True).strip():
        raise ValueError('Commit source and confirmation protocol before decoding')
    development = Path(plan['development'])
    subprocess.run([sys.executable, str(development / 'verify-correction.py.txt'), '--repo', str(repo),
                    '--plan', str(development / 'plan.json'), '--output', str(development),
                    '--dependency-root', str(dependency_root)], check=True)
    model = get_model('parakeet-tdt-0-6b-v3-int8')
    if not installation_ready(model, model_dir, check_hashes=True):
        raise ValueError('Provide the complete pinned Parakeet model')
    tokenizer = json.loads((tokenizer_dir / 'receipt.json').read_bytes())
    if (not tokenizer['all_token_ids_match'] or tokenizer['pieces'] != 8192
            or tokenizer['tokens_sha256'] != file_digest(model_dir / 'tokens.txt')
            or tokenizer['vocab_sha256'] != file_digest(tokenizer_dir / 'tokenizer.vocab')
            or tokenizer['tokenizer_sha256'] != file_digest(tokenizer_dir / 'tokenizer.model')):
        raise ValueError('Authentic tokenizer receipt or bytes changed')
    model_files = {item['path']: file_digest(model_dir / item['path']) for item in model['files']}
    _original, cohorts = load_corpus(plan['corpus_path'])
    clips = cohorts['reserved_confirmation']
    output.mkdir(parents=True, exist_ok=False)
    (output / 'plan.json').write_bytes(plan_bytes)
    write_new(output / 'started.json', {'source': source, 'source_clean': True, 'plan_sha256': sha256(plan_bytes),
                                       'expected_native_decodes': len(clips) * 2, 'expected_records': len(clips) * len(plan['arms']), 'complete': False})
    cases, native = [], {}
    started = time.perf_counter()
    NetworkGuard.install()
    try:
        import sherpa_onnx
        if sherpa_onnx.__version__ != '1.13.4':
            raise ValueError('Use the frozen sherpa runtime')
        disable_sherpa_telemetry(sherpa_onnx)
        with (output / 'cases.jsonl').open('x', encoding='utf-8', newline='\n') as journal:
            for arm in (BASELINE, HINT):
                engine = sherpa_onnx.OfflineRecognizer.from_transducer(
                    encoder=str(model_dir / 'encoder.int8.onnx'), decoder=str(model_dir / 'decoder.int8.onnx'),
                    joiner=str(model_dir / 'joiner.int8.onnx'), tokens=str(model_dir / 'tokens.txt'),
                    model_type='nemo_transducer', num_threads=4, provider='cpu',
                    decoding_method='greedy_search' if arm == BASELINE else 'modified_beam_search',
                    max_active_paths=4, hotwords_score=1.5, modeling_unit='bpe', bpe_vocab=str(tokenizer_dir / 'tokenizer.vocab'))
                native[arm] = []
                for i, clip in enumerate(clips):
                    audio, rate = sf.read(clip['audio_path'], dtype='float32')
                    if rate != 16000 or audio.ndim != 1 or len(audio) != clip['num_samples'] or not np.isfinite(audio).all():
                        raise ValueError('Reserved audio dimensions changed')
                    text, error = '', None
                    before = time.perf_counter()
                    try:
                        stream = engine.create_stream(' / '.join(plan['terms'])) if arm == HINT else engine.create_stream()
                        stream.accept_waveform(16000, audio)
                        engine.decode_stream(stream)
                        text = stream.result.text
                        del stream
                    except Exception as exc:
                        error = type(exc).__name__
                    row = {key: clip[key] for key in ('id', 'source_filename', 'reference', 'role')}
                    row.update(arm=arm, audio_sha256=clip['sha256'], raw=text, text=text, error=error, stages=[],
                               seconds=time.perf_counter() - before)
                    native[arm].append(row)
                    cases.append(row)
                    journal.write(json.dumps(row, ensure_ascii=False) + '\n')
                    journal.flush()
                    if (i + 1) % 10 == 0 or i + 1 == len(clips):
                        print(json.dumps({'arm': arm, 'completed': i + 1, 'expected': len(clips)}), flush=True)
                del engine
                gc.collect()
            corrector = DictionaryCorrector(plan['terms'])
            for arm in plan['candidates']:
                for old, hinted in zip(native[BASELINE], native[HINT], strict=True):
                    text, stages, error = old['text'], [], old['error'] or hinted['error']
                    if error is None:
                        if arm == ALLOWED[1]:
                            result = corrector.correct(text, language='en', hint=hinted['text'])
                            stages.append(asdict(result))
                            text = result.text
                        result = corrector.correct(text, language='en')
                        stages.append(asdict(result))
                        text = result.text
                        if any(stage['reason'] in ('correction_unavailable', 'phonetic_unavailable', 'frequency_unavailable', 'invalid_dictionary') for stage in stages):
                            error = 'CorrectionUnavailable'
                    row = {key: old[key] for key in ('id', 'source_filename', 'reference', 'role', 'audio_sha256', 'raw')}
                    row.update(arm=arm, text=text, error=error, stages=stages)
                    cases.append(row)
                    journal.write(json.dumps(row, ensure_ascii=False) + '\n')
        report = {**summarize(cases, plan), 'source': source, 'source_clean': True,
                  'plan_sha256': sha256(plan_bytes), 'plan_unchanged': plan_bytes == plan_path.read_bytes(),
                  'model_files': model_files, 'model_files_unchanged': all(file_digest(model_dir / name) == value for name, value in model_files.items()),
                  'corpus_unchanged': file_digest(plan['corpus_path']) == plan['corpus_sha256'],
                  'development_unchanged': all(file_digest(development / name) == value for name, value in plan['development_files'].items()),
                  'package_unchanged': package_identity() == plan['package'], 'runtime': sherpa_onnx.__version__,
                  'seconds': time.perf_counter() - started, 'native_decodes': len(clips) * 2,
                  'only_audio_cohort_decoded': 'reserved_confirmation', 'bengali_tamil_telugu_audio_decoded': False,
                  'python_network_guard': NetworkGuard.is_installed(), 'native_firewall_verified': False,
                  'scope': 'public_English_separate_recordings_shared_prompts_speaker_independence_unverified'}
        write_new(output / 'report.json', report)
        return report
    finally:
        NetworkGuard.uninstall()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--freeze', type=Path, help='Verified development evidence folder')
    parser.add_argument('--corpus', type=Path)
    parser.add_argument('--model-dir', type=Path)
    parser.add_argument('--tokenizer-dir', type=Path)
    parser.add_argument('--dependency-root', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    if args.freeze:
        if not args.corpus:
            parser.error('Provide the original explicit corpus')
        write_new(args.plan, make_plan(args.freeze, args.corpus))
        print(json.dumps({'plan_sha256': file_digest(args.plan), 'audio_decoded': False}))
    else:
        if not all((args.model_dir, args.tokenizer_dir, args.dependency_root, args.output)):
            parser.error('Provide explicit existing model, tokenizer, dependency and new output folders')
        result = evaluate(args.plan, args.model_dir, args.tokenizer_dir, args.dependency_root, args.output)
        print(json.dumps({key: result[key] for key in ('complete', 'confirmation_gate_passed', 'chosen_candidate', 'ship_accepted')}))


if __name__ == '__main__':
    main()
