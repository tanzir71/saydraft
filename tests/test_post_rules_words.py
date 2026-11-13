"""Public native-bakeoff regressions and the grammar edits cleanup still permits."""

import pytest

from saydraft.cleanup.llm.validate import validate_llm_output
from saydraft.eval import EvalCase, execute_case
from tests.test_cleanup_bakeoff import pipeline_for


@pytest.mark.parametrize('intensity', [1, 2, 3])
@pytest.mark.parametrize('source,candidate', [
    ('Envoyez le rapport à toute notre équipe demain', 'Envélez le rapport à toute notre équipe demain'),
    ('The plugin configuration is stable for every project in this workspace while automated integration checks verify production behavior',
     'The plagin configuration is stable for every project in this workspace while automated integration checks verify production behavior'),
    ('Send the report from Alice to Bob before the whole team meets for lunch',
     'Send the report from Bob to Alice before the whole team meets for lunch'),
    ('Keep the draft confidential while the whole team reviews the current proposal',
     'Keep the draft while the whole team reviews the current proposal'),
    ('অফিসে পুরো দলের সাথে প্রতিবেদনটি পর্যালোচনা করুন',
     'অফিসে পুরো দলের সাথে প্রতিবেদন্টি পর্যালোচনা করুন'),
    ('أرسل التقرير إلى كل أعضاء الفريق صباحًا', 'أرسل التقریر إلى كل أعضاء الفريق صباحًا'),
])
def test_post_rules_cleanup_cannot_silently_replace_drop_or_reorder_content(source, candidate, intensity):
    assert validate_llm_output(source, candidate, intensity=intensity).ok
    result = validate_llm_output(source, candidate, intensity=intensity, post_rules=True)
    assert not result.ok and result.reason == 'post_rules_words_changed'


@pytest.mark.parametrize('source,candidate', [
    ('The files is ready for your review', 'The files are ready for your review'),
    ('The files was ready for your review', 'The files were ready for your review'),
    ('The whole team have access to the complete draft in the shared workspace',
     'The whole team has access to the complete draft in the shared workspace'),
    ("I'm ready to send the final report to our whole team once the review is complete",
     'I am ready to send the final report to our whole team once the review is complete'),
    ('Send the report to the team after we finish reviewing the current draft and collect every remaining comment',
     'Please send the report to the team after we finish reviewing the current draft and collect every remaining comment'),
    ('We are gonna review the proposal with the whole team after the current draft is ready',
     'We are going to review the proposal with the whole team after the current draft is ready'),
    ('Envoyez le rapport à toute notre e\u0301quipe demain', 'Envoyez le rapport à toute notre équipe demain.'),
    ('বাংলায় কথা বলছি', 'বাংলায় কথা বলছি।'),
    ('أرسل التقرير إلى الفريق', 'أرسل التقرير إلى الفريق.'),
])
def test_punctuation_unicode_and_bounded_grammar_or_style_edits_stay_eligible(source, candidate):
    assert validate_llm_output(source, candidate, post_rules=True).ok


def test_tense_changes_are_not_subject_verb_agreement_corrections():
    source = 'The files are ready for review by the whole team in the current workspace'
    candidate = source.replace('are', 'were', 1)
    assert validate_llm_output(source, candidate, post_rules=True).reason == 'post_rules_words_changed'


def test_explicit_polished_rewording_and_translation_keep_their_existing_contracts():
    source = 'The task is big enough for the whole team to handle today'
    candidate = source.replace('big', 'large')
    assert validate_llm_output(source, candidate, intensity=4, post_rules=True).ok
    assert not validate_llm_output(source, candidate, intensity=3, post_rules=True).ok
    assert validate_llm_output('Envoyez le rapport à toute notre équipe',
        'Send the report to our whole team', translate=True, post_rules=True).ok


@pytest.mark.parametrize('stage', ['true', 1, None])
def test_rules_stage_requires_an_explicit_boolean(stage):
    assert validate_llm_output('Hello', 'Hello', post_rules=stage).reason == 'invalid_stage'


def test_the_observed_native_french_substitution_falls_back_through_the_real_client_and_pipeline():
    source = 'Envoyez le rapport à toute notre équipe demain'
    pipeline, observer = pipeline_for('Envélez le rapport à toute notre équipe demain')
    try:
        result = execute_case(EvalCase('native-language-08', source, source, 'balanced', 'general'), pipeline)
        assert result.cleaned_text == source
        assert pipeline.last_llm_decision == 'rejected:post_rules_words_changed'
        assert observer.reply['client_reason'] == 'ok' and observer.reply['source_tokens'] > 0
    finally:
        pipeline.close()
