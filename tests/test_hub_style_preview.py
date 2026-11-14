"""Actual Hub previews must agree with the delivery processor and authored goldens."""
import copy
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from saydraft.core.interfaces import TargetContext
from saydraft.core.processing import IdentityFormatter, TranscriptProcessor
from saydraft.core.style_preview import render_style_preview
from saydraft.dictation import DictationConfig, DictationPipeline
from saydraft.dictation.glossary import Glossary, load_glossary
from saydraft.insert.inserter import InsertionResult
from saydraft.ui.styles_page import GROUP_LABELS
from tests.test_hub import subject as subject


@pytest.fixture(autouse=True)
def preserve_existing_history(subject):
    before = subject.store.list_recent(limit=100)
    yield
    assert subject.store.list_recent(limit=100) == before


def engine_preview(request):
    pipeline = DictationPipeline(DictationConfig(drop_message_period=request.drop_message_period),
        llm_cleaner=NS(available=lambda: False))
    pipeline.glossary = request.glossary
    history, deliveries = [], []
    def insert(text, **options):
        deliveries.append(text)
        return InsertionResult('inserted', 'memory', enter_sent=options.get('send_enter', False))
    processor = TranscriptProcessor(cleaner=pipeline, formatter=IdentityFormatter(),
        history=NS(append=lambda entry: history.append(entry) or len(history)),
        inserter=NS(insert_text=insert), snippets=dict(request.snippets),
        voice_enter_enabled=request.voice_enter_enabled, reporter=NS(report=lambda *args: None))
    result = processor.process(request.text, context=request.context,
        target=TargetContext('owned-memory', request.context.app_title, app_group=request.context.app_group),
        model='public-text-fixture', language=request.context.language)
    assert history[0].raw_text == request.text
    assert deliveries == ([result.cleaned_text] if result.cleaned_text else [])
    return result.cleaned_text


def select(combo, value):
    index = combo.findData(value)
    assert index >= 0, value
    combo.setCurrentIndex(index)


def test_real_hub_all_84_styles_match_authored_goldens_and_delivery_engine(subject):
    from saydraft.eval import load_eval_corpus
    hub = subject.hub
    page = hub.settings_page.styles_page
    hub.settings_page.profile_combo.setCurrentText('general')
    hub.show_page('Style')
    assert hub.pages.currentWidget() is page and page.window() is hub
    select(page.language, 'en')
    expected = {(c.app_group, c.tone, c.intensity): c.expected
        for c in load_eval_corpus() if c.id.startswith('style-v1-')}
    assert len(expected) == 84
    original = subject.config.read_bytes()
    for group in GROUP_LABELS:
        select(page.group, group)
        for tone in ('formal', 'casual', 'very_casual'):
            select(page.tones[group], tone)
            for level in range(1, 5):
                select(page.levels[group], level)
                page.refresh()
                request = page._request()
                assert page.after.toPlainText() == engine_preview(request) == expected[group, tone, level]
    assert subject.config.read_bytes() == original


@pytest.mark.parametrize('code,text', [
    ('en', 'ask Krezle about 14 files.'), ('ar', 'أرسل 14 ملفًا إلى مريم.'),
    ('bn', 'রহিমকে 14টি ফাইল পাঠান।'), ('pt', 'Envie 14 arquivos para Maria.'),
    ('zh', '请把14个文件发给小明。'), ('tl', 'Ipadala ang 14 na file kay Maria.'),
    ('fr', 'Envoyez 14 fichiers à Marie.'), ('de', 'Senden Sie 14 Dateien an Maria.'),
    ('hi', 'मरियम को 14 फ़ाइलें भेजें।'), ('id', 'Kirim 14 berkas kepada Maria.'),
    ('ja', 'マリアに14個のファイルを送ってください。'), ('ko', '마리아에게 파일 14개를 보내 주세요.'),
    ('ms', 'Hantar 14 fail kepada Maria.'), ('fa', '14 پرونده را برای مریم بفرستید.'),
    ('es', 'Envía 14 archivos a María.'), ('ta', 'மரியாவுக்கு 14 கோப்புகளை அனுப்பவும்.'),
    ('te', 'మరియాకు 14 ఫైళ్లు పంపండి.'), ('th', 'ส่งไฟล์14ไฟล์ให้มาเรีย'),
    ('ur', 'مریم کو 14 فائلیں بھیجیں۔'), ('vi', 'Gửi 14 tệp cho Maria.'),
])
def test_requested_language_previews_match_engine_without_speech_or_config_changes(subject, code, text):
    settings = subject.hub.settings_page
    page = settings.styles_page
    settings.dictionary_editor.setPlainText(json.dumps({'user_terms': ['Krezel']}))
    select(page.language, code)
    select(page.group, 'general')
    page.before.setPlainText(text)
    before = subject.config.read_bytes()
    page.refresh()
    assert page._request().context.language == code
    assert page.after.toPlainText() == engine_preview(page._request())
    if code == 'en':
        assert page.after.toPlainText() == 'Ask Krezel about 14 files.'
    else:
        assert page.after.toPlainText() == text
    assert subject.config.read_bytes() == before
    assert settings._collect_config()['stt']['language'] == 'auto'


def test_auto_follows_draft_speech_settings_and_explicit_preview_choice_stays_local(subject):
    settings = subject.hub.settings_page
    page = settings.styles_page
    page.refresh()
    assert page._request().context.language == 'auto'
    assert 'Choose a preview language' in page.status.text()
    speech = settings.languages_page.combos[0]
    select(speech, 'ar')
    page.refresh()
    assert page._request().context.language == 'ar'
    select(page.language, 'en')
    select(speech, 'bn')
    page.refresh()
    assert page._request().context.language == 'en'
    assert settings._collect_config()['stt']['language'] == 'bn'
    select(page.language, None)
    page.refresh()
    assert page._request().context.language == 'bn'
    names = [page.language.itemText(i) for i in range(1, page.language.count())]
    assert names == sorted(names)
    assert any('Brazilian Portuguese' in name for name in names)


def test_pending_dictionary_form_is_previewed_without_staging_claims_or_writing(subject):
    settings = subject.hub.settings_page
    page, dictionary = settings.styles_page, settings.dictionary_page
    select(page.language, 'en')
    select(page.group, 'general')
    page.before.setPlainText('ask Krezle about 14 files.')
    before = (subject.directory / 'glossary.json').read_bytes()
    draft = dictionary.json_editor.toPlainText()
    claims = copy.deepcopy(dictionary.manual_claims)
    dictionary.term_edit.setText('Krezel')
    page.refresh()
    assert page.after.toPlainText() == 'Ask Krezel about 14 files.'
    assert page.after.toPlainText() == engine_preview(page._request())
    assert dictionary.json_editor.toPlainText() == draft and dictionary.manual_claims == claims
    assert (subject.directory / 'glossary.json').read_bytes() == before
    assert 'Krezel' not in load_glossary(str(subject.directory / 'glossary.json')).user_terms
    assert settings.apply_changes()
    assert 'Krezel' in load_glossary(str(subject.directory / 'glossary.json')).user_terms
    page.refresh()
    assert page.after.toPlainText() == 'Ask Krezel about 14 files.'


def test_staged_protection_replacements_and_snippets_use_the_same_order_as_delivery(subject):
    settings = subject.hub.settings_page
    page = settings.styles_page
    select(page.language, 'en')
    select(page.group, 'general')
    settings.dictionary_editor.setPlainText(json.dumps({'user_terms': ['Krezel'],
        'protected_terms': ['Krezle'], 'replacements': {'sea sharp': 'C#'}}))
    settings.snippets_editor.setPlainText('sig=Keep Krezle unchanged\n')
    page.before.setPlainText('ask Krezle about sea sharp. sig')
    page.refresh()
    assert page.after.toPlainText() == engine_preview(page._request())
    assert 'Krezle' in page.after.toPlainText() and 'Krezel' not in page.after.toPlainText()
    assert 'C#' in page.after.toPlainText() and 'Keep Krezle unchanged' in page.after.toPlainText()


def test_invalid_dictionary_draft_refuses_rules_and_ai_without_discarding_edits(subject):
    settings = subject.hub.settings_page
    page = settings.styles_page
    calls = []
    page.callback = lambda request: calls.append(request) or True
    settings.dictionary_editor.setPlainText('{broken')
    page.preview_ai()
    assert not page.after.toPlainText() and not page.ai_button.isEnabled() and not calls
    assert 'Dictionary JSON is invalid' in page.status.text()
    assert settings.dictionary_editor.toPlainText() == '{broken'


def test_clean_dictionary_uses_live_provider_but_staged_edits_take_precedence(subject):
    settings = subject.hub.settings_page
    page = settings.styles_page
    settings.style_glossary_provider = lambda: Glossary(user_terms=('Krezel',))
    select(page.language, 'en')
    select(page.group, 'general')
    page.before.setPlainText('ask Krezle.')
    page.refresh()
    assert page.after.toPlainText() == 'Ask Krezel.'
    settings.dictionary_editor.setPlainText(json.dumps({'protected_terms': ['Krezle']}))
    page.refresh()
    assert page.after.toPlainText() == 'Ask Krezle.'


def test_stale_ai_result_cannot_replace_new_dictionary_or_language_preview(subject):
    from saydraft.core.style_preview import StylePreviewResult
    settings = subject.hub.settings_page
    page = settings.styles_page
    calls = []
    page.callback = lambda request: calls.append(request) or True
    page.preview_ai()
    first = calls[-1]
    settings.dictionary_page.term_edit.setText('Krezel')
    page.accept_result(StylePreviewResult(first, 'STALE DICTIONARY', 'accepted'))
    assert 'STALE DICTIONARY' not in page.after.toPlainText()
    page.preview_ai()
    second = calls[-1]
    select(page.language, 'ar')
    page.accept_result(StylePreviewResult(second, 'STALE LANGUAGE', 'accepted'))
    assert 'STALE LANGUAGE' not in page.after.toPlainText()


def test_cleanup_preview_does_not_inherit_spoken_translation_target(subject):
    settings = subject.hub.settings_page
    page = settings.styles_page
    select(settings.tier_combo, 'pro')
    settings.labs_page.command.translate_check.setChecked(True)
    page.translation_targets['general'] = 'ar'
    settings.dictionary_editor.setPlainText(json.dumps({'user_terms': ['Krezel']}))
    select(page.group, 'general')
    select(page.language, 'en')
    page.before.setPlainText('ask Krezle.')
    page.refresh()
    assert page._request().context.translation_target == ''
    assert page.after.toPlainText() == 'Ask Krezel.'
    direct = replace(page._request(), context=replace(page._request().context, translation_target='ar'))
    assert render_style_preview(direct).text == 'Ask Krezel.'


def test_hub_preview_replays_all_96_qualified_dictionary_outputs(subject):
    proof = Path(__file__).resolve().parents[1] / 'eval/asr/results/2026-11-15-dictionary-correction'
    plan = json.loads((proof / 'plan.json').read_bytes())
    rows = [json.loads(line) for line in (proof / 'pipeline/cases.jsonl').read_text('utf-8').splitlines()]
    assert len(rows) == 96
    settings = subject.hub.settings_page
    page = settings.styles_page
    settings.dictionary_editor.setPlainText(json.dumps({'user_terms': plan['terms']}))
    settings.profile_combo.setCurrentText('general')
    select(page.language, 'en')
    select(page.group, 'general')
    select(page.tones['general'], 'casual')
    select(page.levels['general'], 2)
    for row in rows:
        page.before.setPlainText(row['raw_asr'])
        page.refresh()
        if row['raw_asr']:
            assert page.after.toPlainText() == engine_preview(page._request()) == row['candidate_cleaned'], (row['phase'], row['id'])
        else:
            assert not page.after.toPlainText()  # Empty preview is invalid, as before.
