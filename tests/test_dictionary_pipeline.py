import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from saydraft.core.interfaces import TargetContext
from saydraft.core.processing import IdentityFormatter, TranscriptProcessor
from saydraft.dictation import DictationConfig, DictationContext, DictationPipeline
from saydraft.dictation.dictionary_correction import DictionaryVocabulary
from saydraft.dictation.glossary import Glossary, protect_terms, restore_terms
from saydraft.dictation.protect import protect_spans, restore_spans
from saydraft.insert.inserter import InsertionResult


def pipeline(terms=('Krezel',), *, protected=(), replacements=(), llm=None):
    result = DictationPipeline(DictationConfig(), llm_cleaner=llm or SimpleNamespace(available=lambda: False))
    result.glossary = Glossary(tuple(terms), tuple(protected), tuple(replacements))
    return result


def context(**kwargs):
    return DictationContext(language='en', intensity=2, **kwargs)


def test_real_pipeline_corrects_known_english_dictionary_before_cleanup():
    cleaner = pipeline()
    assert cleaner.process_for_delivery('Ask Krezle.', context()) == 'Ask Krezel.'
    assert len(cleaner.last_dictionary_result.edits) == 1 and cleaner.last_timings['dictionary'] >= 0


def test_original_asr_is_saved_before_memory_insertion_and_corrected_output_is_delivered():
    cleaner = pipeline()
    saved, inserted = [], []
    processor = TranscriptProcessor(cleaner=cleaner, formatter=IdentityFormatter(),
        history=SimpleNamespace(append=lambda entry: saved.append(entry) or 1),
        inserter=SimpleNamespace(insert_text=lambda text, **kwargs: inserted.append(text) or InsertionResult('inserted', 'memory')))
    result = processor.process('Ask Krezle.', target=TargetContext('memory', 'Fixture'),
                               context=context(), model='fixture-asr', language='en')
    assert result.raw_text == saved[0].raw_text == 'Ask Krezle.'
    assert result.cleaned_text == saved[0].cleaned_text == inserted[0] == 'Ask Krezel.'
    assert json.loads(saved[0].timings_json)['dictionary'] >= 0


@pytest.mark.parametrize('ctx', [
    DictationContext(language='en', mode='raw'), DictationContext(language='en', intensity=1),
    DictationContext(language='en', app_group='code'), DictationContext(language='en', profile='code/comments'),
    DictationContext(language='auto'), DictationContext(language='bn'), DictationContext(language='pt-BR'),
    DictationContext(language='en', translation_target='es'),
])
def test_ineligible_contexts_do_not_apply_dictionary_guesses(ctx):
    cleaner = pipeline()
    output = cleaner.process_for_delivery('Ask Krezle.', ctx)
    assert 'Krezle' in output and cleaner.last_dictionary_result is None


def test_mixed_scripts_and_protected_terms_preserve_the_original_name():
    cleaner = pipeline(protected=['Krezle'])
    assert 'Krezle' in cleaner.process_for_delivery('Ask Krezle.', context())
    assert not cleaner.last_dictionary_result.edits
    cleaner = pipeline()
    assert 'Krezle' in cleaner.process_for_delivery('Ask Krezle বাংলা.', context())
    assert cleaner.last_dictionary_result is None


def test_explicit_replacement_destination_outranks_a_fuzzy_dictionary_entry():
    cleaner = pipeline(replacements=[('alias', 'Krezle')])
    assert cleaner.process_for_delivery('Ask alias.', context()) == 'Ask Krezle.'
    assert not cleaner.last_dictionary_result.edits


def test_corrected_names_are_protected_from_llm_and_nested_placeholders_do_not_collide():
    seen = []
    llm = SimpleNamespace(available=lambda: True, clean=lambda text, **kwargs: (seen.append(text) or text, 'ok'))
    cleaner = pipeline(['Krezel', 'Marion'], llm=llm)
    raw = '"Marion" and Krezle __GLOSSARY_0__'
    output = cleaner.process_for_delivery(raw, context())
    assert output == '"Marion" and Krezel __GLOSSARY_0__'
    assert 'Krezel' not in seen[0] and 'Krezle' not in seen[0]
    assert len(cleaner.last_dictionary_result.edits) == 1


def test_more_than_forty_entries_are_supported_and_ambiguity_is_global():
    terms = ['Quxnobita' + chr(97 + i // 26) + chr(97 + i % 26) for i in range(80)] + ['Krezel']
    cleaner = pipeline(terms)
    assert cleaner.process_for_delivery('Ask Krezle.', context()) == 'Ask Krezel.'
    cleaner = pipeline([*terms, 'Kresel'])
    assert cleaner.process_for_delivery('Ask Krezle.', context()) == 'Ask Krezle.'


def test_unsupported_long_entry_does_not_disable_other_names_or_lose_protection():
    long = 'x' * 65
    cleaner = pipeline([long, 'Krezel'])
    assert cleaner.process_for_delivery(f'Ask Krezle {long}.', context()) == f'Ask Krezel {long}.'


def test_cache_reuses_vocabulary_and_learning_rebuilds_global_ambiguity():
    cleaner = pipeline()
    cleaner.process_for_delivery('Ask Krezle.', context())
    first = cleaner._dictionary_vocabulary
    cleaner.process_for_delivery('Ask Krezle again.', context())
    assert cleaner._dictionary_vocabulary is first
    cleaner.learn_word('Kresel')
    assert cleaner.process_for_delivery('Ask Krezle.', context()) == 'Ask Krezle.'
    assert cleaner._dictionary_vocabulary is not first
    cleaner.process_for_delivery('No dictionary needed.', DictationContext(language='bn'))
    assert cleaner.last_dictionary_result is None and 'dictionary' not in cleaner.last_timings


def test_compiled_production_vocabulary_replays_every_qualified_output():
    proof = Path(__file__).resolve().parents[1] / 'eval/asr/results/2026-11-15-dictionary-correction'
    plan = json.loads((proof / 'plan.json').read_bytes())
    terms = plan['terms']
    vocabulary = DictionaryVocabulary(terms)
    checked = 0
    for directory in (proof, proof / 'confirmation'):
        rows = [json.loads(line) for line in (directory / 'cases.jsonl').read_text(encoding='utf-8').splitlines()]
        baseline = {row['id']: row for row in rows if row['arm'] == 'parakeet_greedy'}
        candidate = {row['id']: row for row in rows if row['arm'] == 'parakeet_greedy__phonetic'}
        for identifier, row in baseline.items():
            protected, mapping = protect_terms(row['text'], Glossary(user_terms=tuple(terms)))
            protected, spans = protect_spans(protected, protected_tokens=mapping)
            actual = vocabulary.correct(protected, language='en')
            restored = restore_terms(restore_spans(actual.text, spans), mapping)
            assert restored == candidate[identifier]['text'], (directory.name, identifier)
            checked += 1
    assert checked == 96
