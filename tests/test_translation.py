"""Translation policy/validation uses authored text and no model/device access."""

from types import SimpleNamespace as NS

import pytest

from saydraft.cleanup.llm.edit import EditReply
from saydraft.config import default_config, save_config, load_config
from saydraft.core.preferences import select_context
from saydraft.models.command import command_choice, translation_choice
from saydraft.translation import instruction, sanitize_targets, translate, validate_translation


def test_targets_are_explicit_group_preferences_and_upgrade_default_off(tmp_path):
    cfg = default_config()
    assert not cfg['labs']['translate_mode'] and not cfg['translation']['targets']
    cfg['translation']['targets'] = {'general': 'es', 'email': 'ar', 'code': 'es', 'invented': 'en', 'docs': True}
    path = tmp_path / 'config.json'
    saved = save_config(cfg, path)
    assert saved['translation']['targets'] == {'general': 'es', 'email': 'ar'}
    assert load_config(config_path=path)['translation'] == saved['translation']
    assert select_context(saved, [], None).translation_target == ''
    saved['labs']['translate_mode'] = True
    assert select_context(saved, [], None).translation_target == 'es'
    assert select_context(saved, [], None, app_group='email').translation_target == 'ar'
    saved['dictation']['mode'] = 'raw'
    assert select_context(saved, [], None).translation_target == ''
    assert sanitize_targets([]) == {}


def test_translation_and_command_admission_are_independent_and_keep_cleanup_defaults():
    cfg = default_config()
    cfg['app']['tier'] = 'pro'
    cfg['labs']['translate_mode'] = True
    assert translation_choice(cfg).reason == 'ready' and command_choice(cfg).reason == 'disabled'
    cfg['app']['tier'] = 'standard'
    assert translation_choice(cfg).reason == 'needs_pro'
    cfg['labs']['translate_mode'] = False
    cfg['labs']['command_mode'] = True
    assert translation_choice(cfg).reason == 'disabled'


@pytest.mark.parametrize('source,target,candidate', [
    ('The file is ready.', 'es', 'El archivo está listo.'),
    ('El archivo no está listo.', 'en', 'The file is not ready.'),
    ('The meeting starts at 10:30.', 'ar', 'يبدأ الاجتماع في 10:30.'),
    ('الاجتماع يبدأ في 10:30.', 'en', 'The meeting starts at 10:30.'),
])
def test_bidirectional_examples_allow_language_change(source, target, candidate):
    assert validate_translation(source, target, candidate).ok


@pytest.mark.parametrize('source,target,candidate,reason', [
    ('Start at 10:30.', 'es', 'Empieza a las 30:10.', 'times_changed'),
    ('Date: 2026-11-14.', 'es', 'Fecha: 2026-14-11.', 'dates_changed'),
    ('Cost 10 USD.', 'es', 'Cuesta 10 EUR.', 'currency_changed'),
    ('Pay $10 and €20.', 'es', 'Paga $20 y €10.', 'amounts_changed'),
    ('The file is ready.', 'ar', 'The file is ready.', 'target_script_missing'),
    ('The file is ready.', 'en', 'الملف جاهز.', 'target_script_missing'),
    ('Email a@example.com.', 'es', 'Envía b@example.com.', 'emails_changed'),
])
def test_mechanical_preservation_and_target_script_guards(source, target, candidate, reason):
    assert validate_translation(source, target, candidate).reason == reason


def test_unchanged_wrong_language_is_not_claimed_as_translation_and_cancel_discards_reply():
    assert validate_translation('Hola.', 'en', 'Hola.', source_language='es').reason == 'not_translated'
    active = [True]
    def edit(source, command, **options):
        assert source == 'The file is ready.' and command == instruction('es')
        active[0] = False
        return EditReply('El archivo está listo.', 'ok', stream_complete=True)
    assert translate(NS(edit_selection=edit), 'The file is ready.', 'es', cancelled=lambda: not active[0]).reason == 'cancelled'


@pytest.mark.parametrize('target', ['', 'auto', 'fr', None, []])
def test_invalid_target_never_invokes_a_model(target):
    editor = NS(edit_selection=lambda *a, **kw: pytest.fail('Invalid target reached model'))
    assert translate(editor, 'Speech', target).reason == 'invalid_target'


def test_partial_response_is_not_a_translation():
    editor = NS(edit_selection=lambda *a, **kw: EditReply('El archivo está listo.', 'ok'))
    assert translate(editor, 'The file is ready.', 'es').reason == 'incomplete'


def test_literal_code_is_hidden_from_translation_and_restored_in_one_pass_without_slot_collisions():
    calls = []
    source = 'Use __SPAN_0__ and `YES __SPAN_1__`.'
    def edit(text, command, **kwargs):
        calls.append(text)
        assert text == 'Use __SPAN_0__ and __SPAN_2__.' and 'YES' not in text
        return EditReply('Usa __SPAN_0__ y __SPAN_2__.', 'ok', stream_complete=True)
    result = translate(NS(edit_selection=edit), source, 'es', source_language='en')
    assert result.reason == 'ok' and result.text == 'Usa __SPAN_0__ y `YES __SPAN_1__`.' and len(calls) == 1


def test_missing_opaque_literal_slot_is_rejected_and_code_only_is_allowed_unchanged():
    bad = NS(edit_selection=lambda *a, **kw: EditReply('Usa SÍ.', 'ok', stream_complete=True))
    assert translate(bad, 'Use `YES`.', 'es').reason == 'placeholders_changed'
    same = NS(edit_selection=lambda text, *a, **kw: EditReply(text, 'ok', stream_complete=True))
    assert translate(same, '`YES`', 'ar', source_language='en').text == '`YES`'


def test_authored_native_corpus_covers_both_required_pairs_and_literal_code():
    import json
    from pathlib import Path
    cases = [json.loads(line) for line in Path('tests/translation_cases.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(cases) == len({c['id'] for c in cases}) == 10
    assert {(c['source_language'], c['target_language']) for c in cases} == {('en', 'es'), ('es', 'en'), ('en', 'ar'), ('ar', 'en')}
    assert all(c['required'] and all(c['required']) for c in cases)
    literal = next(c for c in cases if c['id'] == 'en-es-untrusted-code')
    assert '`YES`' in literal['selection'] and ['`YES`'] in literal['required']
