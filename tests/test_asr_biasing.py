import builtins
import itertools
import unicodedata

import pytest

from saydraft.asr import biasing
from saydraft.asr.biasing import DictionaryCorrector, damerau_levenshtein


EMPTY = frozenset()


def correct(text, terms=('Krezel',), phonetic=None, **kwargs):
    return DictionaryCorrector(terms, phonetic=phonetic).correct(text, language='en', word_set=EMPTY, **kwargs)


def test_real_double_metaphone_spelling_correction_retains_original_and_offsets():
    result = correct('Ask Krezle, please.')
    assert result.raw == 'Ask Krezle, please.' and result.text == 'Ask Krezel, please.'
    edit, = result.edits
    assert edit.before == result.raw[edit.start:edit.end] == 'Krezle'
    assert edit.after == edit.term == 'Krezel' and edit.distance == 1
    assert edit.evidence == 'phonetic' and result.reason == 'corrected'


def test_true_damerau_distance_not_restricted_optimal_string_alignment():
    assert damerau_levenshtein('ca', 'abc') == 2
    assert damerau_levenshtein('krezle', 'krezel') == 1
    assert damerau_levenshtein('', 'abc') == 3
    assert damerau_levenshtein('', '') == 0
    for a, b in itertools.product(('ab', 'ba', 'abc', 'bca', ''), repeat=2):
        assert damerau_levenshtein(a, b) == damerau_levenshtein(b, a)
    with pytest.raises(ValueError):
        damerau_levenshtein('x' * 65, 'x')


@pytest.mark.parametrize('text', ["Krezle's report.", 'Krezle’s report.'])
def test_possessive_suffix_bytes_are_preserved(text):
    assert correct(text).text == text.replace('Krezle', 'Krezel')


def test_phrase_correction_preserves_existing_word_case_and_whitespace():
    result = correct('Ask Krezle\t  Cluster.', ('Krezel cluster',))
    assert result.text == 'Ask Krezel\t  Cluster.'
    assert result.edits[0].before == 'Krezle\t  Cluster'


def test_normalized_unicode_name_comparison_does_not_normalize_other_text():
    text = unicodedata.normalize('NFD', 'Ask Klocker, café.')
    result = correct(text, ('Klöcker',))
    assert result.text == text.replace('Klocker', 'Klöcker')
    canonical = unicodedata.normalize('NFD', 'Ask Klöcker, café.')
    assert correct(canonical, ('Klöcker',)).text == canonical


@pytest.mark.parametrize('language', ['auto', 'de', 'bn', 'ar', 'zh', 'ja', 'ko', 'th', 'pt-BR', '', None])
def test_unsupported_languages_never_receive_english_phonetic_rewrites(language):
    text = 'Ask Krezle.'
    result = DictionaryCorrector(['Krezel']).correct(text, language=language, word_set=EMPTY)
    assert result.text == text and not result.edits


def test_english_region_is_supported_but_code_mode_and_mixed_scripts_abstain():
    engine = DictionaryCorrector(['Krezel'])
    assert engine.correct('Krezle.', language='en-US', word_set=EMPTY).text == 'Krezel.'
    assert engine.correct('Krezle.', language='en', code_mode=True, word_set=EMPTY).text == 'Krezle.'
    for text in ('Krezle বাংলা', 'Krezle العربية', 'Krezle 日本語', 'Krezle α'):
        assert engine.correct(text, language='en', word_set=EMPTY).text == text


@pytest.mark.parametrize('text', [
    '`Krezle`', '```python\nKrezle\n```', '```\nKrezle', '`Krezle',
    '"Krezle"', '“Krezle”', '"Krezle', "'Krezle'",
    'https://example.com/Krezle', 'http://Krezle.com', 'name@Krezle.com',
    'Krezle.com', 'ftp://server/Krezle', 'C:\\path\\Krezle', '/usr/Krezle',
    'obj.Krezle', 'Krezle.attribute', 'Krezle_id', 'aKrezle', 'Krezle2',
    '#Krezle', '@Krezle', '$Krezle', '--Krezle', 'KREZLE', 'Krezle-worker',
    'Krezle\u0301suffix', '__SPAN_0__',
])
def test_literals_identifiers_numbers_and_unicode_word_boundaries_are_preserved(text):
    assert correct(text).text == text


def test_protected_terms_and_existing_dictionary_phrases_never_change():
    for protected in (['Krezle'], ['Ask Krezle'], ['ASK KREZLE']):
        engine = DictionaryCorrector(['Krezel'], protected_terms=protected)
        assert engine.correct('Ask Krezle.', language='en', word_set=EMPTY).text == 'Ask Krezle.'
    assert correct('Krezle cluster.', ['Krezel', 'Krezle cluster']).text == 'Krezle cluster.'
    protected = unicodedata.normalize('NFD', 'Klöcker')
    engine = DictionaryCorrector(['Klocker'], protected_terms=[protected])
    assert engine.correct('Klöcker.', language='en', word_set=EMPTY).text == 'Klöcker.'


def test_common_originals_and_unknown_wordlist_fail_closed(monkeypatch):
    engine = DictionaryCorrector(['Krezel'])
    assert engine.correct('Krezle.', language='en', word_set=frozenset({'krezle'})).text == 'Krezle.'
    monkeypatch.setattr(biasing, 'common_words', lambda _language: None)
    assert engine.correct('Krezle.', language='en').reason == 'frequency_unavailable'


def test_real_bundled_wordlist_prevents_homophone_replacement():
    assert 'brian' in biasing.common_words('en')
    result = DictionaryCorrector(['Bryan']).correct('Please ask Brian.', language='en')
    assert result.text == result.raw and not result.edits


def test_phonetic_ambiguity_preserves_original_even_if_one_spelling_is_closer():
    assert correct('Krezle.', ['Krezel', 'Kresel']).text == 'Krezle.'


def test_edit_distance_alone_or_phonetic_code_alone_is_insufficient():
    assert correct('Krezle.', phonetic=None).text == 'Krezel.'
    engine = DictionaryCorrector(['Krezel'], phonetic=lambda word: (word.upper(), ''))
    assert engine.correct('Krezle.', language='en', word_set=EMPTY).text == 'Krezle.'
    engine = DictionaryCorrector(['Krezel'], phonetic=lambda _word: ('SAME', ''))
    assert engine.correct('Unrelated.', language='en', word_set=EMPTY).text == 'Unrelated.'


def test_hints_transfer_only_dictionary_spans_preserving_numbers_articles_and_punctuation():
    result = correct('Ask Krezle for four files, please.', hint='Ask Krezel for 4 documents!')
    assert result.text == 'Ask Krezel for four files, please.'
    assert result.edits[0].evidence == 'phonetic_context'
    assert correct('The task belongs to Krezel.', hint='A task belongs to Krezel!').text == 'The task belongs to Krezel.'


def test_hints_cannot_insert_names_delete_words_or_override_safety():
    for hint in ('Ask Krezel now.', 'Ask another person.', 'Krezle, Krezel', ''):
        result = correct('Krezle.', hint=hint)
        assert result.text == 'Krezle.'
    result = DictionaryCorrector(['Krezel'], protected_terms=['Krezle']).correct(
        'Ask Krezle.', hint='Ask Krezel.', language='en', word_set=EMPTY)
    assert result.text == 'Ask Krezle.'


def test_two_corrections_are_applied_using_original_offsets():
    result = correct('Krezle; Krezle.')
    assert result.text == 'Krezel; Krezel.' and len(result.edits) == 2
    for edit in result.edits:
        assert result.raw[edit.start:edit.end] == edit.before


@pytest.mark.parametrize('terms', [['Krezel', 'krezel'], ['x' * 65], ['Krezel'] * 41, 'Krezel', None, [42]])
def test_invalid_or_excessive_dictionary_is_rejected_without_truncation(terms):
    result = correct('Krezle.', terms)
    assert result.reason == 'invalid_dictionary' and result.text == 'Krezle.'


def test_limits_and_failed_dependencies_preserve_the_entire_input(monkeypatch):
    assert correct('Krezle ' * 513).text == 'Krezle ' * 513
    assert correct('Krezle ' * 17).reason == 'edit_limit'
    assert correct('Krezle', hint='x' * 4097).text == 'Krezle'
    engine = DictionaryCorrector(['Krezel'], phonetic=lambda _word: (_ for _ in ()).throw(RuntimeError()))
    assert engine.correct('Krezle.', language='en', word_set=EMPTY).reason == 'correction_unavailable'
    original = builtins.__import__
    def blocked(name, *args, **kwargs):
        if name == 'metaphone':
            raise ImportError('explicit missing optional dependency')
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', blocked)
    assert correct('Krezle.').reason == 'phonetic_unavailable'
