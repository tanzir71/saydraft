import copy
import gzip
import io
import json
from pathlib import Path
import tarfile

import pytest

from tools import dictionary_names_corpus as corpus
from tools.dictionary_names import summarize


@pytest.fixture
def fixture(monkeypatch, tmp_path):
    seed = tuple(('Name' + chr(97 + i // 26) + chr(97 + i % 26), i) for i in range(40))
    lines = []
    for identifier in range(60):
        text = seed[identifier][0] + ' has arrived.' if identifier < 40 else (
            f'At {identifier} people arrived.' if identifier < 50 else 'Other people arrived.')
        for recording in (2, 1):  # Input order must not choose cohorts.
            lines.append(f'{identifier}\t{identifier:03}{recording}.wav\t{text}\t{text.lower()}\t0\t32000\tMALE')
    metadata = ('\n'.join(lines) + '\n').encode()
    monkeypatch.setattr(corpus, 'SEED', seed)
    monkeypatch.setattr(corpus, 'METADATA_SHA256', corpus.sha256(metadata))
    exclusions = {'ids': [999], 'sources': [{'path': 'earlier/corpus.json', 'sha256': 'reference-only'}],
                  'inference_performed': False}
    plan = corpus.make_plan(metadata, exclusions)
    path = tmp_path / 'plan.json'
    corpus.write_new(path, plan)
    (tmp_path / 'dev.tsv').write_bytes(metadata)
    return tmp_path, metadata, exclusions, plan


def archive_for(plan, *, alter=None):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w') as archive:
        directory = tarfile.TarInfo('dev')
        directory.type = tarfile.DIRTYPE
        archive.addfile(directory)
        for rows in plan['cohorts'].values():
            for row in rows:
                member = tarfile.TarInfo('dev/' + row['source_filename'])
                data = ('fake audio: ' + row['source_filename']).encode()
                member.size = len(data)
                if alter:
                    member, data = alter(member, data)
                    if member is None:
                        continue
                archive.addfile(member, io.BytesIO(data) if member.isfile() else None)
    return gzip.compress(buffer.getvalue(), mtime=0)


def prepare_archive(monkeypatch, fixture, *, alter=None):
    root, metadata, exclusions, plan = fixture
    payload = archive_for(plan, alter=alter)
    monkeypatch.setattr(corpus, 'ARCHIVE_BYTES', len(payload))
    monkeypatch.setattr(corpus, 'ARCHIVE_SHA256', corpus.sha256(payload))
    plan = corpus.make_plan(metadata, exclusions)
    (root / 'plan.json').unlink()
    corpus.write_new(root / 'plan.json', plan)
    return payload, plan


def test_reference_only_names_and_negative_selection_are_frozen(fixture):
    _root, metadata, exclusions, plan = fixture
    assert len(plan['terms']) == len(set(plan['terms'])) == 40
    assert all(row['source_filename'].endswith('1.wav') for row in plan['cohorts']['development'])
    assert all(row['source_filename'].endswith('2.wav') for row in plan['cohorts']['reserved_confirmation'])
    assert [row['role'] for row in plan['cohorts']['development']].count('negative_numeric') == 10
    assert [row['role'] for row in plan['cohorts']['development']].count('negative_other') == 10
    assert corpus.make_plan(metadata, exclusions) == plan
    assert plan['gate']['relative_term_recall_gain_min'] == .30
    assert not plan['inference_performed_at_selection'] and not plan['ship_or_owner_acceptance']


@pytest.mark.parametrize('fault', ['metadata', 'overlap', 'duplicates', 'inference', 'seed', 'gate'])
def test_selection_or_gate_changes_are_refused(monkeypatch, fixture, fault):
    _root, metadata, exclusions, plan = fixture
    if fault == 'metadata':
        metadata += b'changed'
    elif fault == 'overlap':
        exclusions['ids'].append(1)
    elif fault == 'duplicates':
        exclusions['ids'].append(999)
    elif fault == 'inference':
        exclusions['inference_performed'] = True
    elif fault == 'seed':
        monkeypatch.setattr(corpus, 'SEED', (('Absent', 1),) + corpus.SEED[1:])
    else:
        plan['gate']['relative_term_recall_gain_min'] = .01
    with pytest.raises(ValueError):
        corpus.validate_plan(plan, metadata) if fault == 'gate' else corpus.make_plan(metadata, exclusions)


def test_complete_archive_is_verified_and_only_frozen_recordings_are_retained(monkeypatch, fixture):
    root = fixture[0]
    payload, plan = prepare_archive(monkeypatch, fixture)
    result = corpus.acquire(root / 'plan.json', root / 'dev.tsv', root / 'corpus', open_url=lambda _url: io.BytesIO(payload))
    assert result['archive_bytes_read'] == len(payload) and result['full_archive_checksum_verified']
    assert (root / 'corpus/dev.tar.gz').read_bytes() == payload
    loaded, cohorts = corpus.load_corpus(root / 'corpus/corpus.json')
    assert loaded == plan
    assert len(cohorts['development']) == len(cohorts['reserved_confirmation']) == 60
    assert len(list((root / 'corpus/audio').iterdir())) == 120
    with pytest.raises(FileExistsError):
        corpus.acquire(root / 'plan.json', root / 'dev.tsv', root / 'corpus', open_url=lambda _url: io.BytesIO(payload))


@pytest.mark.parametrize('fault', ['short', 'extra', 'hash', 'missing', 'traversal', 'link', 'oversize'])
def test_archive_errors_never_write_a_complete_manifest(monkeypatch, fixture, fault):
    def alter(member, data):
        if fault == 'missing':
            return None, data
        if fault == 'traversal':
            member.name = '../' + member.name
        if fault == 'link':
            member.type = tarfile.SYMTYPE
            member.linkname = 'outside'
        if fault == 'oversize':
            # A highly compressible member exceeds the allowed per-recording limit.
            data = b'x' * (4 * 1024 * 1024 + 1)
            member.size = len(data)
        return member, data

    root = fixture[0]
    # Only one member needs to exercise path/type/size refusal.
    changed = False

    def once(member, data):
        nonlocal changed
        if not changed:
            changed = True
            return alter(member, data)
        return member, data

    payload, _plan = prepare_archive(monkeypatch, fixture, alter=once)
    if fault == 'short':
        payload = payload[:-1]
    elif fault == 'extra':
        payload += b'x'
    elif fault == 'hash':
        payload = bytes([payload[0] ^ 1]) + payload[1:]
    with pytest.raises(ValueError):
        corpus.acquire(root / 'plan.json', root / 'dev.tsv', root / 'failed', open_url=lambda _url: io.BytesIO(payload))
    assert not (root / 'failed/corpus.json').exists()


@pytest.mark.parametrize('fault', ['audio', 'archive', 'reference', 'missing', 'recording_reuse', 'manifest', 'plan'])
def test_changed_or_incomplete_corpus_is_refused(monkeypatch, fixture, fault):
    root = fixture[0]
    payload, _plan = prepare_archive(monkeypatch, fixture)
    receipt = corpus.acquire(root / 'plan.json', root / 'dev.tsv', root / 'corpus', open_url=lambda _url: io.BytesIO(payload))
    row = receipt['cohorts']['development'][0]
    if fault == 'audio':
        (root / 'corpus' / row['audio']).write_bytes(b'changed')
    elif fault == 'archive':
        (root / 'corpus/dev.tar.gz').write_bytes(b'changed')
    elif fault == 'reference':
        row['reference'] = 'changed reference'
    elif fault == 'missing':
        receipt['cohorts']['development'].pop()
    elif fault == 'recording_reuse':
        reserved = receipt['cohorts']['reserved_confirmation'][0]
        data = (root / 'corpus' / row['audio']).read_bytes()
        (root / 'corpus' / reserved['audio']).write_bytes(data)
        reserved.update(sha256=corpus.sha256(data), bytes=len(data))
    elif fault == 'manifest':
        receipt['full_archive_checksum_verified'] = False
    else:
        data = json.loads((root / 'corpus/plan.json').read_bytes())
        data['gate']['relative_term_recall_gain_min'] = .01
        (root / 'corpus/plan.json').write_text(json.dumps(data))
    (root / 'corpus/corpus.json').write_text(json.dumps(receipt))
    with pytest.raises(ValueError):
        corpus.load_corpus(root / 'corpus/corpus.json')


def test_unicode_exact_terms_boundaries_and_repeated_false_positives():
    assert corpus.term_counts('Klo\u0308cker. Klöcker', 'KLÖCKER klöcker klöcker', ['Klöcker']) == {
        'expected': 2, 'matched': 2, 'false_positives': 1}
    assert corpus.term_counts('plate', 'late', ['late']) == {'expected': 0, 'matched': 0, 'false_positives': 1}


def test_number_acronym_diagnostics_preserve_signs_and_do_not_accept_substrings():
    terms = ['NHK']
    assert corpus.protected_errors('CEO paid -4.2% to NHK in 2000.', 'CEO paid 4.2% to NHK in 2000.', terms) == {
        'numbers': 2, 'acronyms': 0}
    assert corpus.protected_errors('CEO paid 20.', 'ceo paid 21.', terms) == {'numbers': 2, 'acronyms': 1}


def passing_cases(plan):
    rows = []
    for arm in corpus.ARMS:
        for index, selected in enumerate(plan['cohorts']['development']):
            text = selected['reference']
            if arm in ('parakeet_greedy', 'whisper_baseline') and index < 20:
                text = text.replace(plan['terms'][index], 'unrecognized')
            rows.append({'arm': arm, 'id': selected['id'], 'source_filename': selected['source_filename'],
                         'reference': selected['reference'], 'role': selected['role'], 'text': text, 'error': None, 'seconds': 1.})
    return rows


def test_relative_gain_requires_all_frozen_pairs_and_never_means_shipping(fixture):
    plan = fixture[-1]
    result = summarize(passing_cases(plan), plan)
    assert result['complete'] and result['development_gate_passed']
    assert all(row['relative_term_recall_gain'] == 1 for row in result['comparisons'].values())
    assert not result['ship_or_owner_acceptance'] and not result['confirmation_inferred']


@pytest.mark.parametrize('reference,changed,metric', [
    ('NHK people arrived.', 'nhk people arrived.', 'acronyms'),
    ('At -40 people arrived.', 'At 40 people arrived.', 'numbers'),
])
def test_protected_surfaces_fail_even_when_normalized_word_and_character_scores_match(fixture, reference, changed, metric):
    from tools.bench_models import score

    plan = copy.deepcopy(fixture[-1])
    selected = plan['cohorts']['development'][-1]
    selected['reference'] = reference
    rows = passing_cases(plan)
    for row in rows:
        if row['id'] == selected['id'] and row['arm'] in corpus.PAIRS:
            row['text'] = changed
    assert score(reference, reference) == score(reference, changed)
    result = summarize(rows, plan)
    assert not result['development_gate_passed']
    assert all(metric in comparison['per_clip_regressions'][0]['metrics'] for comparison in result['comparisons'].values())


@pytest.mark.parametrize('fault', ['gain', 'negative', 'word', 'number', 'acronym', 'missing', 'duplicate', 'failed', 'wrong_id', 'reference', 'filename'])
def test_all_failed_candidates_keep_original_denominators_and_fail_closed(fixture, fault):
    plan = fixture[-1]
    rows = passing_cases(plan)
    for arm in corpus.PAIRS:
        candidate = [row for row in rows if row['arm'] == arm]
        if fault == 'gain':
            for new, old in zip(candidate, [row for row in rows if row['arm'] == corpus.PAIRS[arm]]):
                new['text'] = old['text']
        elif fault == 'negative':
            candidate[-1]['text'] += ' ' + plan['terms'][0]
        elif fault == 'word':
            candidate[-1]['text'] += ' unrelated'
        elif fault == 'number':
            candidate[-1]['text'] += ' -42%'
        elif fault == 'acronym':
            candidate[-1]['text'] += ' CEO'
        elif fault == 'missing':
            rows.remove(candidate[0])
        elif fault == 'duplicate':
            rows.append(copy.deepcopy(candidate[0]))
        elif fault == 'failed':
            candidate[0]['error'] = 'NativeFailure'
        elif fault == 'wrong_id':
            candidate[0]['id'] = 999
        elif fault == 'reference':
            candidate[0]['reference'] = 'Changed reference'
        else:
            candidate[0]['source_filename'] = '999.wav'
    result = summarize(rows, plan)
    assert not result['development_gate_passed'] and not result['ship_or_owner_acceptance']
    assert result['expected_cases'] == len(plan['cohorts']['development']) * len(corpus.ARMS)


def test_real_frozen_reference_selection_does_not_use_hypotheses():
    root = Path(__file__).resolve().parents[1] / 'eval/asr/results/2026-11-14-dictionary-names'
    plan = json.loads((root / 'selection-plan.json').read_bytes())
    corpus.validate_plan(plan, (root / 'dev.tsv').read_bytes())
    assert len(plan['terms']) == 40 and 'Klöcker' in plan['terms']
    assert len(plan['cohorts']['development']) == len(plan['cohorts']['reserved_confirmation'])
    for cohort in plan['cohorts'].values():
        assert {row['role'] for row in cohort} == {'positive', 'negative_numeric', 'negative_other'}
