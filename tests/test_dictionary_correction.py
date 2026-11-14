import copy

import pytest

from tools.dictionary_correction import BASELINES, MODES, summarize


def fixture():
    arms = [*BASELINES, *(f'{base}__{mode}' for base in BASELINES for mode in MODES)]
    plan = {'ids': [1], 'terms': ['Krezel'], 'arms': arms, 'gate': {'relative_term_recall_gain_min': .30}}
    cases = [{'arm': arm, 'id': 1, 'reference': 'Krezel Krezel', 'raw': 'Krezel Krezle',
              'audio_sha256': 'audio', 'source_filename': '1.wav', 'role': 'positive',
              'text': 'Krezel Krezle' if arm in BASELINES else 'Krezel Krezel', 'stages': [], 'error': None}
             for arm in arms]
    return plan, cases


def test_all_candidates_compared_with_their_own_baseline_and_no_ship_claim():
    plan, cases = fixture()
    result = summarize(cases, plan)
    assert result['complete'] and result['development_gate_passed']
    assert all(row['relative_term_recall_gain'] == 1 for row in result['comparisons'].values())
    assert result['chosen_for_confirmation'] == 'parakeet_greedy__context_then_phonetic'
    assert not result['confirmation_inferred'] and not result['ship_or_owner_acceptance']


@pytest.mark.parametrize('fault', ['gain', 'word', 'number', 'acronym', 'false_positive',
                                 'missing', 'duplicate', 'error', 'id', 'reference', 'audio', 'filename', 'role', 'raw', 'zero_baseline'])
def test_incomplete_changed_or_regressing_results_never_pass(fault):
    plan, cases = fixture()
    if fault == 'zero_baseline':
        for row in cases:
            if row['arm'] in BASELINES:
                row['text'] = 'Krezle Krezle'
    for row in copy.copy(cases):
        if row['arm'] in BASELINES:
            continue
        if fault == 'gain':
            row['text'] = row['raw']
        elif fault == 'word':
            row['text'] += ' extra extra'
        elif fault == 'number':
            row['text'] += ' 24'
        elif fault == 'acronym':
            row['text'] += ' NHK'
        elif fault == 'false_positive':
            row['text'] += ' Krezel'
        elif fault == 'missing':
            cases.remove(row)
        elif fault == 'duplicate':
            cases.append(copy.deepcopy(row))
        elif fault == 'error':
            row['error'] = 'CorrectionUnavailable'
        elif fault == 'id':
            row['id'] = 9
        elif fault == 'reference':
            row['reference'] = 'Changed'
        elif fault == 'audio':
            row['audio_sha256'] = 'changed'
        elif fault == 'filename':
            row['source_filename'] = 'changed.wav'
        elif fault == 'role':
            row['role'] = 'negative'
        elif fault == 'raw':
            row['raw'] = 'changed'
    result = summarize(cases, plan)
    assert not result['development_gate_passed'] and result['chosen_for_confirmation'] is None
    assert result['expected_cases'] == 8 and not result['ship_or_owner_acceptance']
