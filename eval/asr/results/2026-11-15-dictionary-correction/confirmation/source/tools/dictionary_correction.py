"""Frozen text-only development evaluation; never decodes confirmation audio."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import time

from tools.dictionary_names_corpus import file_digest, protected_errors, sha256, term_counts, write_new

BASELINES = ('parakeet_greedy', 'whisper_baseline')
HINTS = {'parakeet_greedy': 'parakeet_hotwords', 'whisper_baseline': 'whisper_context'}
MODES = ('phonetic', 'context_transfer', 'context_then_phonetic')
INPUT_SOURCE = '2215cf6c76499774eb4c8b280c8f74ab04ac9191'
SOURCES = ('saydraft/asr/biasing.py', 'tools/dictionary_correction.py')


def package_identity():
    import metaphone

    root = Path(metaphone.__file__).resolve().parent
    version = importlib.metadata.version('Metaphone')
    if version != '0.6':
        raise ValueError('Use the pinned Metaphone version')
    return {'name': 'Metaphone', 'version': version,
            'sdist_sha256': 'ad0beadca66cb7ec6ede71ef72bb02da097c493ddf159930d6340bc83f53da27',
            'python_files': {path.relative_to(root).as_posix(): file_digest(path) for path in sorted(root.rglob('*.py'))}}


def make_plan(evidence):
    root = Path(evidence).resolve()
    selection = json.loads((root / 'selection-plan.json').read_bytes())
    report = json.loads((root / 'report.json').read_bytes())
    if (report['source'] != INPUT_SOURCE or not report['complete'] or report['confirmation_inferred']
            or selection['protocol'] != 'fleurs_dev_names_40_v1'):
        raise ValueError('Supply the original complete frozen development evidence')
    repo = Path(__file__).resolve().parents[1]
    frequency = repo / 'assets/dictionary/frequency/en.txt.gz'
    manifest = json.loads((frequency.parent / 'manifest.json').read_bytes())
    if file_digest(frequency) != manifest['languages']['en']['sha256']:
        raise ValueError('Bundled common-word list bytes changed')
    arms = [*BASELINES, *(f'{base}__{mode}' for base in BASELINES for mode in MODES)]
    return {'schema': 1, 'protocol': 'dictionary_correction_40_v1',
            'scope': 'previously_observed_public_English_development_not_holdout_or_owner_accuracy',
            'input_evidence': str(root),
            'inputs': {name: file_digest(root / name) for name in ('cases.jsonl', 'report.json', 'selection-plan.json', 'corpus.json', 'files.json')},
            'input_native_source': INPUT_SOURCE, 'terms': selection['terms'],
            'ids': [row['id'] for row in selection['cohorts']['development']],
            'baselines': list(BASELINES), 'hint_providers': HINTS, 'modes': list(MODES), 'arms': arms,
            'algorithm': 'Double Metaphone primary/secondary code intersection plus unrestricted Damerau-Levenshtein; unique code target, distance1 for lengths4-5 or2 for length>=6, common original words/protected spans/code/identifiers/ambiguous matches preserved; explicit English only. Hint transfer copies only eligible dictionary spans into baseline; all other baseline bytes retained. Combined mode applies transfer then independent correction, with per-stage offsets.',
            'algorithm_source_lf_sha256': {name: sha256((repo / name).read_bytes().replace(b'\r\n', b'\n')) for name in SOURCES},
            'package': package_identity(), 'frequency': {'file': 'assets/dictionary/frequency/en.txt.gz',
                                                        'sha256': file_digest(frequency), 'words': manifest['languages']['en']['words']},
            'gate': {'relative_term_recall_gain_min': .30, 'no_added_term_false_positives': True,
                     'no_added_per_clip_word_or_character_errors': True,
                     'no_added_per_clip_number_or_acronym_surface_errors': True, 'all_frozen_cases_complete': True},
            'selection_policy': 'Among fully passing development candidates choose greatest exact term recall, then lexical arm name. No confirmation decoding is part of this tool. Freeze and verify a separate confirmation run before production.',
            'confirmation_inferred': False, 'ship_or_owner_acceptance': False}


def summarize(cases, plan):
    from tools.bench_models import score

    selected = [row for row in cases if row['arm'] in BASELINES]
    bases = {base: {row['id']: row for row in selected if row['arm'] == base} for base in BASELINES}
    complete = len(cases) == len(plan['ids']) * len(plan['arms'])
    arms, comparisons = {}, {}
    for arm in plan['arms']:
        rows = [row for row in cases if row['arm'] == arm]
        complete = complete and [row['id'] for row in rows] == plan['ids'] and len({row['id'] for row in rows}) == len(plan['ids'])
        terms, scores, surfaces = Counter(), Counter(), Counter()
        for row in rows:
            terms.update(term_counts(row['reference'], row['text'], plan['terms']))
            scores.update(score(row['reference'], row['text']))
            surfaces.update(protected_errors(row['reference'], row['text'], plan['terms']))
            complete = complete and row.get('error') is None
        arms[arm] = {'cases': len(rows), 'terms': dict(terms), 'scores': dict(scores),
                     'protected_errors': dict(surfaces), 'term_recall': terms['matched'] / terms['expected'] if terms['expected'] else None,
                     'edits': sum(len(stage['edits']) for row in rows for stage in row['stages'])}
    for base in BASELINES:
        for mode in MODES:
            arm = f'{base}__{mode}'
            regressions = []
            for row in (case for case in cases if case['arm'] == arm):
                original = bases[base].get(row['id'])
                if original is None or any(original[key] != row[key] for key in
                    ('reference', 'audio_sha256', 'source_filename', 'role', 'raw')):
                    complete = False
                    continue
                before, after = score(row['reference'], original['text']), score(row['reference'], row['text'])
                old_surface = protected_errors(row['reference'], original['text'], plan['terms'])
                new_surface = protected_errors(row['reference'], row['text'], plan['terms'])
                failed = [key for key in ('word_errors', 'character_errors') if after[key] > before[key]]
                failed += [key for key in old_surface if new_surface[key] > old_surface[key]]
                if term_counts(row['reference'], row['text'], plan['terms'])['false_positives'] > term_counts(row['reference'], original['text'], plan['terms'])['false_positives']:
                    failed.append('term_false_positives')
                if failed:
                    regressions.append({'id': row['id'], 'role': row['role'], 'metrics': failed})
            old, new = arms[base]['term_recall'], arms[arm]['term_recall']
            gain = new / old - 1 if old and new is not None else None
            comparisons[arm] = {'baseline': base, 'relative_term_recall_gain': gain, 'regressions': regressions}
    for arm, comparison in comparisons.items():
        base = comparison['baseline']
        comparison['development_gate_passed'] = bool(complete and comparison['relative_term_recall_gain'] is not None
            and comparison['relative_term_recall_gain'] >= plan['gate']['relative_term_recall_gain_min']
            and not comparison['regressions'] and arms[arm]['terms']['false_positives'] <= arms[base]['terms']['false_positives'])
    passing = [arm for arm, value in comparisons.items() if value['development_gate_passed']]
    chosen = sorted(passing, key=lambda arm: (-arms[arm]['term_recall'], arm))[0] if passing else None
    return {'complete': bool(complete), 'expected_cases': len(plan['ids']) * len(plan['arms']), 'completed_cases': len(cases),
            'arms': arms, 'comparisons': comparisons, 'chosen_for_confirmation': chosen,
            'development_gate_passed': bool(passing), 'confirmation_inferred': False, 'ship_or_owner_acceptance': False}


def evaluate(plan_path, output):
    from saydraft.asr.biasing import DictionaryCorrector
    from saydraft.privacy.netguard import NetworkGuard

    plan_path, output = Path(plan_path), Path(output)
    plan_bytes = plan_path.read_bytes()
    plan = json.loads(plan_bytes)
    if make_plan(plan['input_evidence']) != plan:
        raise ValueError('Frozen input, algorithm, package, wordlist or criteria changed')
    repo = Path(__file__).resolve().parents[1]
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo, text=True).strip():
        raise ValueError('Commit source and frozen protocol before processing outputs')
    # Authenticate every original native case with the separate stdlib verifier.
    subprocess.run([sys.executable, str(Path(plan['input_evidence']) / 'verify-names.py.txt'), '--repo', str(repo)], check=True)
    inputs = [json.loads(line) for line in (Path(plan['input_evidence']) / 'cases.jsonl').read_text(encoding='utf-8').splitlines()]
    by_arm = {arm: [row for row in inputs if row['arm'] == arm] for arm in (*BASELINES, *HINTS.values())}
    for rows in by_arm.values():
        if [row['id'] for row in rows] != plan['ids'] or any(row['error'] is not None for row in rows):
            raise ValueError('Input case identity or denominator changed')
    output.mkdir(parents=True, exist_ok=False)
    (output / 'plan.json').write_bytes(plan_bytes)
    engine = DictionaryCorrector(plan['terms'])
    cases = []
    started = time.perf_counter()
    NetworkGuard.install()
    try:
        with (output / 'cases.jsonl').open('x', encoding='utf-8', newline='\n') as journal:
            for arm in plan['arms']:
                base, _, mode = arm.partition('__')
                for original, hinted in zip(by_arm[base], by_arm[HINTS[base]], strict=True):
                    text, stages, error = original['text'], [], None
                    if mode:
                        transfer = mode != 'phonetic'
                        result = engine.correct(text, language='en', hint=hinted['text'] if transfer else None)
                        stages.append(asdict(result))
                        text = result.text
                        if mode == 'context_then_phonetic':
                            result = engine.correct(text, language='en')
                            stages.append(asdict(result))
                            text = result.text
                        if any(stage['reason'] in ('correction_unavailable', 'phonetic_unavailable', 'frequency_unavailable', 'invalid_dictionary') for stage in stages):
                            error = 'CorrectionUnavailable'
                    row = {key: original[key] for key in ('id', 'source_filename', 'audio_sha256', 'reference', 'role')}
                    row.update(arm=arm, raw=original['text'], text=text, error=error, stages=stages)
                    cases.append(row)
                    journal.write(json.dumps(row, ensure_ascii=False) + '\n')
        report = {**summarize(cases, plan), 'source': source, 'source_clean': True, 'plan_sha256': sha256(plan_bytes),
                  'plan_unchanged': plan_bytes == plan_path.read_bytes(),
                  'inputs_unchanged': all(file_digest(Path(plan['input_evidence']) / name) == value for name, value in plan['inputs'].items()),
                  'package_unchanged': package_identity() == plan['package'], 'seconds': time.perf_counter() - started,
                  'python_network_guard': NetworkGuard.is_installed(), 'native_firewall_verified': False,
                  'audio_decoded': False, 'offsets_relative_to_stage_input': True, 'scope': plan['scope']}
        write_new(output / 'report.json', report)
        return report
    finally:
        NetworkGuard.uninstall()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--freeze', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    if args.freeze:
        plan = make_plan(args.freeze)
        write_new(args.plan, plan)
        print(json.dumps({'plan_sha256': file_digest(args.plan), 'output_processing_performed': False, 'cases': len(plan['ids']) * len(plan['arms'])}))
    else:
        if not args.output:
            parser.error('Supply a new output folder')
        report = evaluate(args.plan, args.output)
        print(json.dumps({key: report[key] for key in ('complete', 'development_gate_passed', 'chosen_for_confirmation', 'confirmation_inferred')}))


if __name__ == '__main__':
    main()
