"""Freeze and acquire a reference-only FLEURS dev glossary; never runs ASR.

This protocol is deliberately separate from the existing test-split baseline.
All selection precedes inference. Confirmation recordings share the reference
prompts; neither speaker independence nor unseen text is claimed.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
import time
import unicodedata
import urllib.request

from tools.fetch_asr_corpus import REVISION, SOURCE, parse_references

METADATA_SHA256 = '9d57ee7e91e9d4c92edb39f6bbea668ef8dc2a3ff96eb510d5580b2ad05d17ec'
ARCHIVE_SHA256 = '2658fda72f199e12676ecac9415094667a4e14e149b146e568ea00b2a2f0954c'
ARCHIVE_BYTES = 171250900
PREFIX = f'{SOURCE}/resolve/{REVISION}/data/en_us'
SEED = (
    ('Martelly', 1515), ('Manila', 1518), ('Mediterranean', 1525),
    ('Maciej', 1527), ('Krezel', 1527), ('Ogarzynska', 1527), ('Seork', 1527),
    ('Siminoff', 1529), ('Chhappan', 1532), ('Bhog', 1532), ('Shyam', 1532),
    ('Timbuktu', 1534), ('Fairmont', 1538), ('Marion', 1538), ('Kundalini', 1540),
    ('Johndroe', 1542), ('Kashiwazaki', 1547), ('Kariwa', 1547), ('Niigata', 1547),
    ('Klöcker', 1556), ('Ehrenstrahl', 1556), ('Comoros', 1571), ('Mayotte', 1571),
    ('Lakkha', 1578), ('Bishkek', 1584), ('Gingrich', 1591), ('Bachmann', 1591),
    ('Galapagos', 1605), ('Versace', 1608), ('Armand', 1608), ('Uthappa', 1609),
    ('Aristarchus', 1615), ('Kruger', 1617), ('Mozambique', 1617), ('Zimbabwe', 1617),
    ('Vinson', 1618), ('Velasquez', 1630), ('Honshu', 1634), ('Auckland', 1646),
    ('Canaan', 1648),
)
ARMS = ('parakeet_greedy', 'parakeet_beam', 'parakeet_hotwords',
        'whisper_baseline', 'whisper_context')
PAIRS = {'parakeet_beam': 'parakeet_greedy', 'parakeet_hotwords': 'parakeet_greedy',
         'whisper_context': 'whisper_baseline'}


def normalized(text):
    text = unicodedata.normalize('NFKC', text).casefold()
    return ' '.join(''.join(' ' if unicodedata.category(char)[0] in 'PS' else char
                           for char in text).split())


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def file_digest(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as target:
        json.dump(value, target, ensure_ascii=False, indent=2)
        target.write('\n')


def make_plan(metadata, exclusions):
    if sha256(metadata) != METADATA_SHA256:
        raise ValueError('Provide the pinned English dev metadata unchanged')
    excluded = exclusions.get('ids')
    if (not isinstance(excluded, list) or not excluded or
            any(type(value) is not int for value in excluded) or len(set(excluded)) != len(excluded)
            or exclusions.get('inference_performed') is not False or not exclusions.get('sources')):
        raise ValueError('Provide explicit prior and reserved reference-ID exclusions')
    references = parse_references(metadata)
    groups = defaultdict(list)
    for name, row in references.items():
        groups[row['id']].append({'source_filename': name, **row})
    if set(groups) & set(excluded):
        raise ValueError('Dev reference IDs overlap prior or reserved corpora')
    eligible = {}
    for identifier, rows in sorted(groups.items()):
        values = sorted(rows, key=lambda row: row['source_filename'])
        if (len({row['reference'] for row in values}) != 1 or
                len({row['normalized_reference'] for row in values}) != 1):
            raise ValueError('Inconsistent reference text for a repeated utterance ID')
        values = [row for row in values if 16000 <= row['num_samples'] <= 60 * 16000]
        if len(values) >= 2:
            eligible[identifier] = values
    terms = [term for term, _ in SEED]
    keys = {normalized(term) for term in terms}
    if len(keys) != 40 or any(len(key.split()) != 1 for key in keys):
        raise ValueError('Need forty distinct single-token glossary names')
    for term, identifier in SEED:
        if identifier not in eligible or normalized(term) not in normalized(eligible[identifier][0]['reference']).split():
            raise ValueError('Curated name must occur in its unmodified source reference')
    positive, numeric, other = [], [], []
    for identifier, rows in eligible.items():
        text = rows[0]['reference']
        if keys & set(normalized(text).split()):
            positive.append(identifier)
        elif re.search(r'\d', text):
            numeric.append(identifier)
        else:
            other.append(identifier)
    if min(len(numeric), len(other)) < 10:
        raise ValueError('Need ten numeric and ten other negative utterances')
    negatives = numeric[:10] + other[:10]
    ids = sorted(positive + negatives)
    cohorts = {}
    for index, cohort in enumerate(('development', 'reserved_confirmation')):
        cohorts[cohort] = [{**eligible[identifier][index], 'cohort': cohort,
                           'role': 'positive' if identifier in positive else 'negative_numeric'
                           if identifier in numeric[:10] else 'negative_other'} for identifier in ids]
    return {
        'schema': 1, 'protocol': 'fleurs_dev_names_40_v1', 'dataset': 'google/fleurs',
        'revision': REVISION, 'license': 'CC-BY-4.0', 'language': 'en', 'config': 'en_us', 'split': 'dev',
        'metadata_sha256': METADATA_SHA256, 'archive_sha256': ARCHIVE_SHA256,
        'archive_bytes': ARCHIVE_BYTES, 'exclusions': exclusions,
        'selection': 'Forty manually curated personal/place names from raw references, before inference; no hypotheses used. Include every eligible positive utterance, then first ten numeric and first ten other negatives by utterance ID. Choose first and second eligible source filenames lexically for development and reserved confirmation.',
        'seed': [{'term': term, 'source_id': identifier} for term, identifier in SEED],
        'terms': terms, 'cohorts': cohorts, 'arms': list(ARMS), 'pairs': PAIRS,
        'parameters': {'threads': 4, 'parakeet_max_active_paths': 4, 'parakeet_hotwords_score': 1.5,
                       'whisper_beam_size': 5, 'whisper_language': 'en', 'whisper_compute_type': 'int8',
                       'whisper_vad_filter': False, 'whisper_condition_on_previous_text': False,
                       'whisper_context_parameter': 'hotwords', 'whisper_context': ', '.join(terms)},
        'gate': {'relative_term_recall_gain_min': .30, 'no_added_term_false_positives': True,
                 'no_added_per_clip_word_or_character_errors': True,
                 'no_added_per_clip_number_or_protected_token_errors': True,
                 'all_frozen_cases_complete': True},
        'protected_metric': 'Exact multiset distance of numeric surfaces and uppercase acronym tokens in reference and hypothesis, NFKC; glossary names excluded. Diagnostic surface preservation, not semantic equivalence.',
        'confirmation_policy': 'Do not infer reserved recordings unless a development candidate passes every frozen gate. Shared reference prompts; speaker identity unverified; not unseen text or owner acceptance.',
        'inference_performed_at_selection': False, 'ship_or_owner_acceptance': False,
    }


def validate_plan(plan, metadata):
    if make_plan(metadata, plan.get('exclusions', {})) != plan:
        raise ValueError('Frozen plan, reference selection or gate changed')


def _open(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'Saydraft-public-evaluation/0.1',
                                                  'Accept-Encoding': 'identity'})
    return urllib.request.urlopen(request, timeout=30)


def acquire(plan_path, metadata_path, output, *, open_url=_open):
    plan_path, metadata_path, output = map(Path, (plan_path, metadata_path, output))
    plan_bytes, metadata = plan_path.read_bytes(), metadata_path.read_bytes()
    plan = json.loads(plan_bytes)
    validate_plan(plan, metadata)
    if output.exists():
        raise FileExistsError('Choose a new acquisition directory')
    output.mkdir(parents=True)
    (output / 'plan.json').write_bytes(plan_bytes)
    (output / 'dev.tsv').write_bytes(metadata)
    started, deadline = time.monotonic(), time.monotonic() + 600
    compressed = output / 'dev.tar.gz'
    digest, transferred = hashlib.sha256(), 0
    with open_url(f'{PREFIX}/audio/dev.tar.gz') as response, compressed.open('xb') as target:
        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError('Archive transfer deadline exceeded')
            block = response.read(min(1024 * 1024, ARCHIVE_BYTES - transferred + 1))
            if not block:
                break
            transferred += len(block)
            if transferred > ARCHIVE_BYTES:
                raise ValueError('Archive transfer exceeds pinned size')
            digest.update(block)
            target.write(block)
    if transferred != ARCHIVE_BYTES or digest.hexdigest() != ARCHIVE_SHA256:
        raise ValueError('Full compressed archive size or SHA-256 does not match publisher')
    selected = {row['source_filename']: row for rows in plan['cohorts'].values() for row in rows}
    if len(selected) != sum(map(len, plan['cohorts'].values())):
        raise ValueError('Cohorts must have disjoint recording filenames')
    audio_dir = output / 'audio'
    audio_dir.mkdir()
    found, expanded = {}, 0
    with tarfile.open(compressed, 'r|gz') as archive:
        for member in archive:
            if time.monotonic() >= deadline:
                raise TimeoutError('Archive processing deadline exceeded')
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or '\\' in member.name:
                raise ValueError('Unexpected archive member; no filesystem extraction is used')
            if member.isdir():
                continue
            if not member.isfile() or not re.fullmatch(r'[0-9]+\.wav', path.name):
                raise ValueError('Only regular numeric WAV archive members are supported')
            if not 1 <= member.size <= 4 * 1024 * 1024:
                raise ValueError('Unexpected audio member size')
            expanded += member.size
            if expanded > 512 * 1024 * 1024:
                raise ValueError('Expanded audio budget exceeded')
            if path.name not in selected:
                continue
            if path.name in found:
                raise ValueError('Duplicate selected archive recording')
            source = archive.extractfile(member)
            if source is None:
                raise ValueError('Unreadable selected recording')
            payload = source.read(member.size + 1)
            if len(payload) != member.size:
                raise ValueError('Truncated selected recording')
            with (audio_dir / path.name).open('xb') as target:
                target.write(payload)
            found[path.name] = {'sha256': sha256(payload), 'bytes': len(payload), 'audio': f'audio/{path.name}'}
    if set(found) != set(selected):
        raise ValueError('Archive is missing frozen selected recordings')
    receipt = {'schema': 1, 'protocol': plan['protocol'], 'plan_sha256': sha256(plan_bytes),
               'metadata_sha256': sha256(metadata), 'archive_url': f'{PREFIX}/audio/dev.tar.gz',
               'archive_bytes_read': transferred, 'archive_sha256': digest.hexdigest(),
               'full_archive_checksum_verified': True, 'expanded_audio_bytes': expanded,
               'dataset': 'google/fleurs', 'revision': REVISION, 'license': 'CC-BY-4.0',
               'license_url': 'https://creativecommons.org/licenses/by/4.0/',
               'changes': 'Original audio bytes and raw references retained unchanged; subset copied locally.',
               'cohorts': {cohort: [{**row, **found[row['source_filename']]} for row in rows]
                           for cohort, rows in plan['cohorts'].items()},
               'seconds': time.monotonic() - started, 'inference_performed': False, 'complete': True}
    write_new(output / 'corpus.json', receipt)
    (output / 'NOTICE.md').write_text(
        f'# Public FLEURS dev audio\n\nBy the Google FLEURS contributors. {SOURCE}\n'
        f'Revision `{REVISION}`; CC-BY-4.0: https://creativecommons.org/licenses/by/4.0/.\n'
        'Audio and references unchanged. Source names/hashes are in corpus.json.\n'
        'This dataset is separate from the Saydraft MIT license.\n', encoding='utf-8')
    return receipt


def load_corpus(corpus_path):
    path = Path(corpus_path).resolve()
    root = path.parent
    if path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError('Corpus manifest too large')
    receipt = json.loads(path.read_bytes())
    plan_bytes = (root / 'plan.json').read_bytes()
    plan = json.loads(plan_bytes)
    validate_plan(plan, (root / 'dev.tsv').read_bytes())
    if (receipt.get('schema') != 1 or receipt.get('protocol') != plan['protocol']
            or receipt.get('plan_sha256') != sha256(plan_bytes) or receipt.get('metadata_sha256') != METADATA_SHA256
            or receipt.get('archive_sha256') != ARCHIVE_SHA256 or receipt.get('archive_bytes_read') != ARCHIVE_BYTES
            or receipt.get('full_archive_checksum_verified') is not True or receipt.get('complete') is not True
            or receipt.get('dataset') != 'google/fleurs' or receipt.get('revision') != REVISION
            or receipt.get('license') != 'CC-BY-4.0' or receipt.get('inference_performed') is not False
            or set(receipt.get('cohorts', {})) != set(plan['cohorts'])):
        raise ValueError('Incomplete or changed corpus receipt')
    archive = root / 'dev.tar.gz'
    if (not archive.resolve().is_relative_to(root) or archive.stat().st_size != ARCHIVE_BYTES
            or file_digest(archive) != ARCHIVE_SHA256):
        raise ValueError('Retained complete archive bytes changed')
    seen_names, seen_hashes = set(), set()
    cohorts = {}
    for cohort, expected in plan['cohorts'].items():
        rows = receipt['cohorts'][cohort]
        if len(rows) != len(expected):
            raise ValueError('Frozen corpus denominator changed')
        cohorts[cohort] = []
        for actual, selected in zip(rows, expected, strict=True):
            name = selected['source_filename']
            audio = (root / 'audio' / name).resolve()
            if (any(actual.get(key) != value for key, value in selected.items())
                    or actual.get('audio') != f'audio/{name}' or name in seen_names
                    or not audio.is_relative_to(root) or not audio.is_file()
                    or not 1 <= audio.stat().st_size <= 4 * 1024 * 1024
                    or audio.stat().st_size != actual.get('bytes') or file_digest(audio) != actual.get('sha256')
                    or actual['sha256'] in seen_hashes):
                raise ValueError('Recording identity, reference or bytes changed or reused')
            seen_names.add(name)
            seen_hashes.add(actual['sha256'])
            cohorts[cohort].append({**actual, 'audio_path': str(audio)})
    return plan, cohorts


def term_counts(reference, hypothesis, terms):
    expected, actual = Counter(normalized(reference).split()), Counter(normalized(hypothesis).split())
    keys = {normalized(term) for term in terms}
    return {'expected': sum(expected[key] for key in keys),
            'matched': sum(min(expected[key], actual[key]) for key in keys),
            'false_positives': sum(max(0, actual[key] - expected[key]) for key in keys)}


def protected_surfaces(text, terms):
    text = unicodedata.normalize('NFKC', text)
    excluded = {normalized(term) for term in terms}
    return {'numbers': re.findall(r'(?<!\w)[+-]?\d+(?:[.,:/-]\d+)*(?:%|[A-Za-z]+)?(?!\w)', text),
            'acronyms': [token for token in re.findall(r'\b[A-Z][A-Z0-9]{1,}\b', text)
                         if normalized(token) not in excluded]}


def protected_errors(reference, hypothesis, terms):
    expected, actual = protected_surfaces(reference, terms), protected_surfaces(hypothesis, terms)
    return {key: sum((Counter(expected[key]) - Counter(actual[key])).values())
                 + sum((Counter(actual[key]) - Counter(expected[key])).values()) for key in expected}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metadata', type=Path, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--exclusions', type=Path)
    parser.add_argument('--acquire', type=Path, help='New output folder; downloads pinned public audio')
    args = parser.parse_args(argv)
    if args.acquire:
        receipt = acquire(args.plan, args.metadata, args.acquire)
        print(json.dumps({'complete': receipt['complete'], 'cohorts': {key: len(rows) for key, rows in receipt['cohorts'].items()},
                          'full_archive_checksum_verified': receipt['full_archive_checksum_verified']}))
    else:
        if not args.exclusions:
            parser.error('Supply exclusions when freezing references')
        plan = make_plan(args.metadata.read_bytes(), json.loads(args.exclusions.read_bytes()))
        write_new(args.plan, plan)
        print(json.dumps({'terms': len(plan['terms']), 'cohorts': {key: len(rows) for key, rows in plan['cohorts'].items()},
                          'inference_performed': False, 'plan_sha256': file_digest(args.plan)}))


if __name__ == '__main__':
    main()
