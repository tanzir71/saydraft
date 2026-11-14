import copy

import pytest

from tools.dictionary_confirmation import ALLOWED, BASELINE, HINT, summarize


def fixture():
    clip = {'id': 1, 'reference': 'Krezel Krezel', 'sha256': 'audio', 'source_filename': '1.wav', 'role': 'positive'}
    plan = {'clips': [clip], 'terms': ['Krezel'], 'candidates': list(ALLOWED),
            'arms': [BASELINE, HINT, *ALLOWED], 'gate': {'relative_term_recall_gain_min': .30}}
    rows = [{**{k: v for k, v in clip.items() if k != 'sha256'}, 'audio_sha256': 'audio',
             'arm': arm, 'error': None, 'stages': [],
             'text': 'Krezel Krezle' if arm in (BASELINE, HINT) else 'Krezel Krezel'} for arm in plan['arms']]
    return plan, rows


def test_confirmation_selects_equal_accuracy_without_an_extra_asr_decode():
    plan, rows = fixture()
    result = summarize(rows, plan)
    assert result['complete'] and result['confirmation_gate_passed']
    assert result['chosen_candidate'] == ALLOWED[0]
    assert result['expected_cases'] == 4 and not result['ship_accepted'] and not result['owner_accuracy_accepted']


@pytest.mark.parametrize('fault', ['gain', 'word', 'number', 'acronym', 'false_positive',
                                 'missing', 'duplicate', 'error', 'id', 'reference', 'audio', 'filename', 'role', 'zero_baseline'])
def test_confirmation_rejects_collateral_errors_and_incomplete_recordings(fault):
    plan, rows = fixture()
    if fault == 'zero_baseline':
        rows[0]['text'] = 'Krezle Krezle'
    for row in copy.copy(rows):
        if row['arm'] not in ALLOWED:
            continue
        if fault == 'gain':
            row['text'] = rows[0]['text']
        elif fault in ('word', 'number', 'acronym', 'false_positive'):
            row['text'] += {'word': ' other words', 'number': ' 20', 'acronym': ' NHK', 'false_positive': ' Krezel'}[fault]
        elif fault == 'missing':
            rows.remove(row)
        elif fault == 'duplicate':
            rows.append(copy.deepcopy(row))
        elif fault == 'error':
            row['error'] = 'NativeFailure'
        elif fault == 'id':
            row['id'] = 99
        elif fault == 'reference':
            row['reference'] = 'changed'
        elif fault == 'audio':
            row['audio_sha256'] = 'changed'
        elif fault == 'filename':
            row['source_filename'] = 'changed.wav'
        elif fault == 'role':
            row['role'] = 'negative'
    result = summarize(rows, plan)
    assert not result['confirmation_gate_passed'] and result['chosen_candidate'] is None
    assert result['expected_cases'] == 4 and not result['ship_accepted']
