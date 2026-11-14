import copy

import pytest

from tools.dictionary_biasing import ARMS, make_plan, summary, term_counts


def test_exact_term_occurrences_do_not_accept_substrings_or_duplicate_hallucinations():
    assert term_counts('Sintra and Sintra', 'Sintra Sintra Sintra sinister', ['Sintra']) == {
        'expected':2,'matched':2,'false_positives':1}
    assert term_counts('plate', 'late', ['late']) == {'expected':0,'matched':0,'false_positives':1}
    assert term_counts('Sintra.', 'SINTRA!', ['Sintra']) == {'expected':1,'matched':1,'false_positives':0}


def rows():
    return [{'arm':arm,'id':1,'error':None,'seconds':1.,'terms':{'expected':40,'matched':20 if arm=='greedy' else 30,'false_positives':0},
             'scores':{'word_errors':5,'character_errors':10}} for arm in ARMS]


def test_relative_recall_gain_and_development_gate_never_imply_shipping_acceptance():
    result=summary(rows())
    assert result['relative_term_recall_gain']==.5 and result['development_gate_passed']
    assert result['ship_or_owner_acceptance'] is False


@pytest.mark.parametrize('fault',['no_gain','false_positive','word_errors','character_errors','missing_arm','failed_case','zero_baseline','wrong_clip','duplicate_clip'])
def test_collateral_errors_incomplete_runs_and_zero_baselines_never_pass(fault):
    cases=copy.deepcopy(rows())
    if fault=='no_gain':
        cases[-1]['terms']['matched']=25
    elif fault=='false_positive':
        cases[-1]['terms']['false_positives']=1
    elif fault in ('word_errors','character_errors'):
        cases[-1]['scores'][fault]+=1
    elif fault=='missing_arm':
        cases.pop(1)
    elif fault=='failed_case':
        cases[-1]['error']='Fixture failure'
    elif fault=='wrong_clip':
        cases[-1]['id']=2
    elif fault=='duplicate_clip':
        cases.extend(copy.deepcopy(cases))
    else:
        cases[0]['terms']['matched']=0
    assert summary(cases)['development_gate_passed'] is False


def test_reference_only_selection_is_stable_and_uses_forty_distinct_words():
    terms=['dictionary'+chr(97+i//26)+chr(97+i%26) for i in range(45)]
    clips=[{'id':1,'sha256':'fixture','language':'en','reference':' '.join(reversed(terms))}]
    plan=make_plan(clips,[])
    assert plan['terms']==sorted(terms)[:40] and len(set(plan['terms']))==40
    assert plan['gate']['relative_term_recall_gain_min']==.30
    clips[0]['hypothesis']='Changing a prior hypothesis cannot select different terms'
    assert make_plan(clips,[])==plan
    clips[0]['language']='bn'
    with pytest.raises(ValueError,match='English only'):
        make_plan(clips,[])


def test_insufficient_reference_terms_are_refused_before_inference():
    with pytest.raises(ValueError,match='forty'):
        make_plan([{'language':'en','reference':'Small fixture'}],[])
