"""Frozen public-development comparison; never changes shipping ASR defaults."""

import argparse
from collections import Counter
import gc
import hashlib
import json
from pathlib import Path
import re
import statistics
import subprocess
import time

from tools.asr_accuracy import digest, load_corpora
from tools.bench_models import normalized, score

ARMS = ('greedy', 'beam', 'beam_hotwords')


def words(text):
    return normalized(text).split()


def make_plan(clips, receipts):
    if any(row['language'] != 'en' for row in clips):
        raise ValueError('This development protocol evaluates English only')
    forms = {}
    for row in clips:
        for value in re.findall(r'(?<!\w)[A-Za-z]{7,}(?!\w)', row['reference']):
            forms.setdefault(value.casefold(), value)
    selected = sorted(forms, key=lambda word: (-len(word), word))[:40]
    if len(selected) != 40:
        raise ValueError('Need forty distinct reference terms before inference')
    return {'schema': 1, 'scope': 'previously_evaluated_public_development_not_holdout_or_owner_accuracy',
        'selection': 'Forty longest distinct ASCII alphabetic reference words of at least seven letters; casefold lexical ties; no hypotheses used',
        'terms': [forms[word] for word in selected], 'corpora': receipts,
        'clips': [{'id': row['id'], 'sha256': row['sha256']} for row in clips],
        'arms': list(ARMS), 'threads': 4, 'max_active_paths': 4, 'hotwords_score': 1.5,
        'gate': {'relative_term_recall_gain_min': .30, 'no_added_term_false_positives': True,
                 'no_added_word_or_character_errors': True, 'all_cases_complete': True},
        'metric': 'Exact casefolded normalized whole-token occurrence recall; excess predicted occurrences are false positives'}


def term_counts(reference, hypothesis, terms):
    expected, actual = Counter(words(reference)), Counter(words(hypothesis))
    terms = {word.casefold() for word in terms}
    return {'expected': sum(expected[term] for term in terms),
        'matched': sum(min(expected[term], actual[term]) for term in terms),
        'false_positives': sum(max(0, actual[term] - expected[term]) for term in terms)}


def summary(cases):
    arms = {}
    for arm in ARMS:
        rows = [row for row in cases if row['arm'] == arm]
        terms, errors = Counter(), Counter()
        for row in rows:
            terms.update(row['terms'])
            errors.update(row['scores'])
        arms[arm] = {'cases': len(rows), 'failures': sum(row.get('error') is not None for row in rows),
            'terms': dict(terms), 'scores': dict(errors),
            'term_recall': terms['matched'] / terms['expected'] if terms['expected'] else None,
            'recognition_p50_seconds': statistics.median(row['seconds'] for row in rows) if rows else None}
    baseline, candidate = arms['greedy'], arms['beam_hotwords']
    base_recall, proposed = baseline['term_recall'], candidate['term_recall']
    gain = proposed / base_recall - 1 if base_recall and proposed is not None else None
    identities = [[row['id'] for row in cases if row['arm'] == arm] for arm in ARMS]
    complete = (baseline['cases'] > 0 and len(set(identities[0])) == len(identities[0])
                and all(values == identities[0] for values in identities)
                and all(arm['cases'] == baseline['cases'] and not arm['failures']
                    and arm['terms']['expected'] == baseline['terms']['expected'] for arm in arms.values()))
    admitted = bool(complete and gain is not None and gain >= .30
        and candidate['terms']['false_positives'] <= baseline['terms']['false_positives']
        and all(candidate['scores'][key] <= baseline['scores'][key] for key in ('word_errors','character_errors')))
    return {'arms': arms, 'relative_term_recall_gain': gain, 'complete': complete,
            'development_gate_passed': admitted, 'ship_or_owner_acceptance': False}


def evaluate(plan_path, model_dir, tokenizer_dir, output):
    import soundfile as sf
    from saydraft.asr.model_ids import DEFAULT_MODEL
    from saydraft.models.downloader import installation_ready
    from saydraft.models.manifest import get_model
    from saydraft.privacy.netguard import NetworkGuard
    from saydraft.privacy.telemetry import disable_sherpa_telemetry

    plan_path, model_dir, tokenizer_dir, output = map(Path, (plan_path, model_dir, tokenizer_dir, output))
    if output.exists():
        raise FileExistsError('Choose a new comparison output directory')
    plan_bytes = plan_path.read_bytes()
    plan = json.loads(plan_bytes)
    clips, receipts = load_corpora([row['path'] for row in plan['corpora']])
    if make_plan(clips, receipts) != plan:
        raise ValueError('Frozen plan, references or gates changed')
    model = get_model(DEFAULT_MODEL)
    if not installation_ready(model, model_dir, check_hashes=True):
        raise ValueError('Provide the complete pinned Parakeet model')
    tokenizer = json.loads((tokenizer_dir / 'receipt.json').read_text(encoding='utf-8'))
    if (not tokenizer.get('all_token_ids_match') or tokenizer.get('pieces') != 8192
            or tokenizer.get('tokens_sha256') != digest(model_dir / 'tokens.txt')
            or tokenizer.get('vocab_sha256') != digest(tokenizer_dir / 'tokenizer.vocab')
            or tokenizer.get('tokenizer_sha256') != digest(tokenizer_dir / 'tokenizer.model')):
        raise ValueError('Authentic tokenizer receipt or bytes changed')
    fingerprints = {name: digest(model_dir / name) for name in (item['path'] for item in model['files'])}
    source = subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip()
    if subprocess.check_output(['git','status','--porcelain'], text=True).strip():
        raise ValueError('Commit the comparison source before native inference')
    output.mkdir(parents=True, exist_ok=False)
    (output / 'plan.json').write_bytes(plan_bytes)
    rows, loads = [], {}
    NetworkGuard.install()
    try:
        import sherpa_onnx
        disable_sherpa_telemetry(sherpa_onnx)
        for arm in ARMS:
            started = time.perf_counter()
            engine = sherpa_onnx.OfflineRecognizer.from_transducer(
                encoder=str(model_dir/'encoder.int8.onnx'), decoder=str(model_dir/'decoder.int8.onnx'),
                joiner=str(model_dir/'joiner.int8.onnx'), tokens=str(model_dir/'tokens.txt'),
                model_type='nemo_transducer', num_threads=4, provider='cpu',
                decoding_method='greedy_search' if arm == 'greedy' else 'modified_beam_search',
                max_active_paths=4, hotwords_score=1.5, modeling_unit='bpe', bpe_vocab=str(tokenizer_dir/'tokenizer.vocab'))
            loads[arm] = time.perf_counter() - started
            for clip in clips:
                audio, rate = sf.read(clip['audio_path'], dtype='float32', always_2d=True)
                if rate != 16000 or len(audio) != clip['num_samples']:
                    raise ValueError('Reference audio dimensions changed')
                started, text, error = time.perf_counter(), '', None
                try:
                    stream = engine.create_stream(' / '.join(plan['terms'])) if arm == 'beam_hotwords' else engine.create_stream()
                    stream.accept_waveform(16000, audio.mean(axis=1))
                    engine.decode_stream(stream)
                    text = stream.result.text
                except Exception as exc:
                    error = type(exc).__name__
                row = {'arm': arm, 'id': clip['id'], 'audio_sha256': clip['sha256'], 'reference': clip['reference'],
                    'text': text, 'error': error, 'seconds': time.perf_counter()-started,
                    'terms': term_counts(clip['reference'], text, plan['terms']), 'scores': score(clip['reference'], text)}
                rows.append(row)
                with (output/'cases.jsonl').open('a',encoding='utf-8') as journal:
                    journal.write(json.dumps(row,ensure_ascii=False)+'\n')
            del stream, engine
            gc.collect()
        result = {**summary(rows), 'source': source, 'source_clean': True,
            'plan_sha256': hashlib.sha256(plan_bytes).hexdigest(), 'model': DEFAULT_MODEL,
            'model_files': fingerprints, 'model_files_unchanged': all(digest(model_dir/name)==value for name,value in fingerprints.items()),
            'plan_unchanged': plan_bytes==plan_path.read_bytes(), 'runtime': sherpa_onnx.__version__,
            'native_load_seconds': loads, 'tokenizer_receipt': tokenizer,
            'python_network_guard': NetworkGuard.is_installed(), 'native_firewall_verified': False,
            'scope': plan['scope'], 'release_latency_or_broad_accuracy_accepted': False}
        (output/'report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        return result
    finally:
        NetworkGuard.uninstall()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze',type=Path,help='Explicit verified public corpus manifest; writes a plan without inference')
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--model-dir',type=Path)
    parser.add_argument('--tokenizer-dir',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.freeze:
        clips,receipts=load_corpora([args.freeze])
        with args.plan.open('x',encoding='utf-8') as output:
            json.dump(make_plan(clips,receipts),output,ensure_ascii=False,indent=2)
        print(json.dumps({'terms':40,'clips':len(clips),'inference_performed':False}))
    else:
        if not all((args.model_dir,args.tokenizer_dir,args.output)):
            parser.error('Provide model, tokenizer and a new output directory')
        result=evaluate(args.plan,args.model_dir,args.tokenizer_dir,args.output)
        print(json.dumps({key:result[key] for key in ('complete','relative_term_recall_gain','development_gate_passed','ship_or_owner_acceptance')}))


if __name__=='__main__':
    main()
