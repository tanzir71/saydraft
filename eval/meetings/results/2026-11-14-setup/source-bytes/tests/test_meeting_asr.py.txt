import copy
from types import SimpleNamespace as NS

import numpy as np
import pytest

from saydraft.asr.model_ids import DEFAULT_MODEL
from saydraft.asr.router import ALL_LANGUAGES, AsrRouter
from saydraft.config import default_config
from saydraft.meetings.asr import MeetingAutoAsr, create_meeting_asr, speech_models


@pytest.mark.parametrize('language', ['ar', 'bn', 'zh', 'hi', 'id', 'ja', 'ko', 'ms', 'fa', 'ta', 'te', 'th', 'ur', 'vi', None])
def test_auto_meetings_retry_unsupported_or_unknown_language_despite_zero_dictation_budget(language):
    config = default_config()
    config['stt']['fallback_budget_ms'] = 0
    calls = []
    def factory(config, route):
        def transcribe(audio):
            calls.append(route.model_id)
            return 'Original script from the correct model' if route.model_id == ALL_LANGUAGES else 'Misrecognized words'
        return NS(transcribe=transcribe, last_language='bn' if route.model_id == ALL_LANGUAGES else None,
                  last_timings={'stt': .1})
    router = AsrRouter(config, engine_factory=factory, installed=lambda _: True,
        language_identifier=NS(identify=lambda _: language))
    asr = MeetingAutoAsr(router)
    assert asr.transcribe(np.zeros(16000)) == 'Original script from the correct model'
    assert calls == [DEFAULT_MODEL, ALL_LANGUAGES]
    assert asr.model_id == ALL_LANGUAGES and asr.last_language == 'bn' and asr.last_timings == {'stt': .1}


@pytest.mark.parametrize('language', ['en', 'es', 'pt', 'fr', 'de'])
def test_confident_supported_chunks_do_not_invoke_a_second_model(language):
    primary = NS(model_id=DEFAULT_MODEL, last_language=language, last_timings={},
                 transcribe=lambda _: 'Confident recognized sentence.',
                 retry_with_model=lambda *args: pytest.fail('No retry needed'))
    assert MeetingAutoAsr(primary).transcribe(np.zeros(16000)) == 'Confident recognized sentence.'


def test_failed_multilingual_retry_never_admits_primary_unsupported_text():
    def fail(*args):
        raise OSError('Fixture model unavailable')
    asr = MeetingAutoAsr(NS(model_id=DEFAULT_MODEL, last_language='bn',
        transcribe=lambda _: 'Wrong primary text', retry_with_model=fail))
    with pytest.raises(OSError):
        asr.transcribe(np.zeros(16000))


def test_router_successful_fallback_is_not_run_twice():
    primary = NS(model_id=ALL_LANGUAGES, last_language='bn', transcribe=lambda _: 'বাংলা',
                 retry_with_model=lambda *args: pytest.fail('Already multilingual'))
    assert MeetingAutoAsr(primary).transcribe(np.zeros(16000)) == 'বাংলা'


def test_prepare_requires_full_verified_shared_model_before_primary_preparation():
    calls = []
    primary = NS(model_id=DEFAULT_MODEL, prepare=lambda: calls.append('prepared'))
    asr = MeetingAutoAsr(primary, resolver=lambda *args, **kwargs: calls.append((args, kwargs)))
    with pytest.raises(FileNotFoundError):
        asr.prepare()
    assert calls == [((ALL_LANGUAGES,), {'check_hashes': True})]
    asr.resolver = lambda *args, **kwargs: 'fixture-verified-directory'
    asr.prepare()
    assert calls[-1] == 'prepared'


def test_meeting_routes_ignore_foreground_overrides_and_leave_saved_config_unchanged(monkeypatch):
    from saydraft.asr import selection
    config = default_config()
    config['stt']['app_model_overrides'] = [{'app_group': 'general', 'model_id': 'whisper-base'}]
    original = copy.deepcopy(config)
    snapshots = []
    monkeypatch.setattr(selection, 'create_asr', lambda cfg: snapshots.append(cfg) or NS(model_id=DEFAULT_MODEL))
    assert type(create_meeting_asr(config)) is MeetingAutoAsr
    assert speech_models(config) == (DEFAULT_MODEL, ALL_LANGUAGES)
    assert snapshots[0]['stt']['app_model_overrides'] == [] and config == original
    config['stt']['pinned_languages'] = ['bn']
    assert not isinstance(create_meeting_asr(config), MeetingAutoAsr)
    assert speech_models(config) == (ALL_LANGUAGES,)
    config['stt']['pinned_languages'] = ['en']
    assert speech_models(config) == (DEFAULT_MODEL,)
    config['stt']['routing_enabled'] = False
    config['stt']['engine'] = 'whisper'
    config['stt']['model_size'] = 'base'
    assert speech_models(config) == ('whisper-base',)
