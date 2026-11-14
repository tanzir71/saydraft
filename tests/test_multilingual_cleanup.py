"""Known non-English speech must not be edited with English word heuristics."""

from dataclasses import replace

import pytest

from saydraft.asr.languages import WHISPER_LANGUAGES
from saydraft.cleanup.formatter import caret_layout, final_punctuation, join_transcripts
from saydraft.cleanup.language import transcript_language
from saydraft.cleanup.llm.validate import validate_llm_output
from saydraft.cleanup.styles import rule_options
from saydraft.dictation import DictationConfig, DictationContext, DictationPipeline


@pytest.mark.parametrize('language', sorted(WHISPER_LANGUAGES - {'en'}))
def test_all_known_non_english_choices_disable_english_lexical_rules(language):
    options = rule_options(DictationContext(language=language, intensity=4, profile='notes'))
    for name in ('remove_fillers', 'aggressive_fillers', 'remove_repetitions', 'handle_self_corrections',
                 'normalize_capitalization', 'enable_list_formatting', 'convert_spoken_punctuation',
                 'convert_spoken_newlines', 'normalize_itn', 'normalize_punctuation'):
        assert getattr(options, name) is False, (language, name)
    assert options.normalize_whitespace is True


@pytest.mark.parametrize('language,text', [
    ('pt', 'Preciso de um livro e de um café.'),
    ('de', 'Er ist hier und er wartet.'),
    ('no', 'Det er en bok.'),
    ('pl', 'i kot, i pies.'),
    ('id', 'Hati hati di jalan.'),
    ('th', 'ค่อย ๆ พูด ไม่ต้องรีบ'),
    ('zh', '不要把三个改成两个。'),
    ('ko', '네 네, 금요일이 아니라 목요일입니다.'),
    ('bn', 'ধীরে ধীরে বলুন।'),
    ('ar', 'لا لا، أريد كتابًا واحدًا.'),
    ('pt-BR', 'Quero um livro, não dois.'),
    ('hi', 'नहीं नहीं, मुझे एक किताब चाहिए।'),
    ('ur', 'نہیں نہیں، مجھے ایک کتاب چاہیے۔'),
    ('ja', 'はいはい、金曜日ではなく木曜日です。'),
    ('vi', 'Tôi cần một cuốn sách, không phải hai.'),
    ('tl', 'Hindi dalawa, isa lang ang kailangan ko.'),
    ('ta', 'எனக்கு ஒரு புத்தகம் வேண்டும்.'),
    ('te', 'నాకు ఒక పుస్తకం కావాలి.'),
    ('fa', 'نه نه، فقط یک کتاب می‌خواهم.'),
    ('fr', 'Un livre, pas deux.'),
    ('ms', 'Saya perlukan satu buku, bukan dua.'),
    ('es', 'Quiero un libro, no dos.'),
])
@pytest.mark.parametrize('level', [1, 2, 3, 4])
def test_rules_preserve_native_words_repetition_negation_and_punctuation(language, text, level):
    pipeline = DictationPipeline(DictationConfig())
    context = DictationContext(language=language, intensity=level, tone='formal', profile='notes')
    assert pipeline.process_transcript(text, context) == text


def test_non_english_final_layout_adds_boundary_gap_without_english_casing_or_stop():
    context = DictationContext(language='pl', tone='formal', before_caret='kot',
                              before_caret_known=True, selection_known=True)
    assert final_punctuation('i pies', context) == 'i pies'
    assert caret_layout('i pies', context) == ' i pies'
    chinese = replace(context, language='zh', before_caret='你好')
    assert caret_layout('世界', chinese) == '世界'
    turkish = replace(context, language='tr', before_caret='')
    assert caret_layout('istanbul', turkish) == 'İstanbul'
    assert caret_layout('istanbul', replace(turkish, language='und')) == 'istanbul'


@pytest.mark.parametrize('level', [2, 3, 4])
def test_non_english_ai_cleanup_cannot_use_english_article_exemptions(level):
    source, candidate = 'Entregue a carta para Maria hoje.', 'Entregue carta para Maria hoje.'
    assert validate_llm_output(source, candidate, intensity=level, post_rules=True, language='pt').reason == 'post_rules_words_changed'
    assert validate_llm_output(source, candidate, post_rules=True, language='en').ok
    assert validate_llm_output(source, source, post_rules=True, language='pt').ok


def test_german_meaning_is_not_lost_to_unicode_casefold_equivalences():
    result = validate_llm_output('Die Maße passen in die Kiste.', 'Die Masse passen in die Kiste.',
                                 post_rules=True, language='de')
    assert not result.ok and result.reason == 'post_rules_words_changed'


def test_native_punctuation_can_split_chinese_without_changing_its_characters():
    assert validate_llm_output('你好世界', '你好，世界。', post_rules=True, language='zh').ok
    assert not validate_llm_output('你好OpenAI世界', '你好Open AI世界', post_rules=True, language='zh').ok


def test_explicit_english_and_legacy_auto_keep_the_existing_cleanup_policy():
    pipeline = DictationPipeline(DictationConfig())
    for language in ('en', 'en-US', 'auto'):
        assert pipeline.process_transcript('um hello hello world.', DictationContext(language=language)) == 'Hello world.'


@pytest.mark.parametrize('detected,preference,segments,expected', [
    (None, 'auto', (), 'und'), (None, 'pt', (), 'pt'), ('pt', 'auto', (), 'pt'),
    ('en', 'auto', ('pt', 'en'), 'mul'), ('en', 'auto', ('', 'en'), 'und'),
    (None, 'en', ('', ''), 'en'), ('fr', 'auto', ('fr', 'fr'), 'fr'),
    (None, 'pt-BR', (), 'pt'), ('invalid', 'auto', (), 'und'),
])
def test_production_language_resolution_preserves_unknown_and_mixed_evidence(detected, preference, segments, expected):
    assert transcript_language(detected, preference, segments=segments) == expected


@pytest.mark.parametrize('parts,expected', [
    (['你好', '世界'], '你好世界'), (['你好。', '世界'], '你好。世界'),
    (['日本', 'の言葉'], '日本の言葉'), (['ค่อย', 'พูด'], 'ค่อยพูด'),
    (['Hello,', 'world.'], 'Hello, world.'), (['3.', '14 books.'], '3. 14 books.'),
    (['한국어', '문장'], '한국어 문장'), (['Quero um', 'livro.'], 'Quero um livro.'),
])
def test_background_join_preserves_script_spacing_and_english_number_boundaries(parts, expected):
    assert join_transcripts(parts) == expected
