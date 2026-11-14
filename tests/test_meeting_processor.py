from types import SimpleNamespace as NS

import pytest

from saydraft.config import default_config
from saydraft.meetings import processor as module
from saydraft.meetings.processor import LocalMeetingProcessor, MeetingPreparationError, prepare_meeting
from saydraft.meetings.summary import SummaryReply
from saydraft.meetings.transcription import MeetingTranscript
from saydraft.models.command import meeting_choice


def fixture(tmp_path, monkeypatch):
    config = default_config()
    config['labs']['notetaker'] = True
    config['app']['tier'] = 'pro'
    config['command']['backend'] = 'cpu'
    calls = []
    editor = NS(close=lambda: calls.append('editor_close'))
    asr = NS(prepare=lambda: calls.append('asr_prepare'))
    diarizer = NS(prepare=lambda: calls.append('speaker_prepare'))
    services = NS(cleaner=NS(llm=NS(command_session=lambda cfg, model: calls.append(('editor', cfg, model)) or editor)),
        history=NS(db_path=tmp_path / 'meeting.db'))
    from saydraft.asr import selection
    from saydraft.models import command, hardware
    monkeypatch.setattr(hardware, 'latest_report', lambda: None)
    monkeypatch.setattr(command, 'installed_command_config', lambda choice, **options: 'verified-fixture-sidecar')
    monkeypatch.setattr(selection, 'create_asr', lambda value: calls.append(('asr_config', value)) or asr)
    monkeypatch.setattr(module, 'SpeakerDiarizer', lambda: diarizer)
    return NS(config=config, calls=calls, editor=editor, asr=asr, diarizer=diarizer, services=services)


@pytest.mark.parametrize('tier', ['lite', 'standard', 'auto'])
def test_meeting_admission_requires_enabled_labs_and_pro_before_model_lease(tmp_path, monkeypatch, tier):
    f = fixture(tmp_path, monkeypatch)
    f.config['app']['tier'] = tier
    with pytest.raises(MeetingPreparationError, match='needs_pro'):
        prepare_meeting(f.services, f.config)
    assert not f.calls


def test_default_notetaker_is_off_and_enabling_it_never_starts_setup():
    config = default_config()
    config['app']['tier'] = 'pro'
    assert config['labs']['notetaker'] is False and meeting_choice(config).reason == 'disabled'
    config['labs']['notetaker'] = True
    assert meeting_choice(config).reason == 'ready'


def test_preparation_uses_saved_language_routing_and_retires_normal_cleanup_before_speech(tmp_path, monkeypatch):
    f = fixture(tmp_path, monkeypatch)
    f.config['stt']['routing_enabled'] = True
    f.config['stt']['pinned_languages'] = ['bn', 'ar']
    processor = prepare_meeting(f.services, f.config)
    assert f.calls[0][0] == 'editor'
    assert f.calls[1] == ('asr_config', f.config)
    assert f.calls[2:] == ['asr_prepare', 'speaker_prepare']
    assert processor.asr is f.asr and processor.diarizer is f.diarizer
    processor.close()
    assert f.calls[-1] == 'editor_close' and processor.asr is None and processor.diarizer is None


def test_text_recovery_does_not_load_any_speech_or_speaker_model(tmp_path, monkeypatch):
    f = fixture(tmp_path, monkeypatch)
    processor = prepare_meeting(f.services, f.config, need_speech=False)
    assert [call[0] for call in f.calls] == ['editor']
    assert processor.asr is None and processor.diarizer is None
    processor.close()


@pytest.mark.parametrize('stage', ['asr', 'speaker', 'store'])
def test_failed_preparation_releases_editing_lease_even_before_processor_construction(tmp_path, monkeypatch, stage):
    f = fixture(tmp_path, monkeypatch)
    def fail():
        raise OSError('Fixture dependency unavailable')
    if stage == 'asr':
        f.asr.prepare = fail
    elif stage == 'speaker':
        f.diarizer.prepare = fail
    else:
        f.services.history = NS()  # Bad NoteStore path port, before processor construction.
    with pytest.raises((OSError, AttributeError)):
        prepare_meeting(f.services, f.config)
    assert f.calls[-1] == 'editor_close'


def test_missing_or_busy_editing_model_never_constructs_speech_engines(tmp_path, monkeypatch):
    f = fixture(tmp_path, monkeypatch)
    from saydraft.models import command
    monkeypatch.setattr(command, 'installed_command_config', lambda *args, **kwargs: None)
    with pytest.raises(MeetingPreparationError, match='model_missing'):
        prepare_meeting(f.services, f.config)
    assert not f.calls
    monkeypatch.setattr(command, 'installed_command_config', lambda *args, **kwargs: object())
    f.services.cleaner.llm.command_session = lambda *args: None
    with pytest.raises(MeetingPreparationError, match='model_busy'):
        prepare_meeting(f.services, f.config)
    assert not f.calls


def test_transcription_releases_exclusive_speech_instances_before_returning_or_raising(monkeypatch):
    observed = []
    def transcribe(audio, **options):
        observed.append((audio, options))
        raise OSError('Fixture recognition failed')
    monkeypatch.setattr(module, 'MeetingTranscriber', lambda *args, **kwargs: NS(transcribe=transcribe))
    processor = LocalMeetingProcessor(object(), object(), None, None)
    with pytest.raises(OSError):
        processor.transcribe('fixture-pcm', cancelled=lambda: False, on_progress=lambda value: None)
    assert processor.asr is None and processor.diarizer is None and observed[0][0] == 'fixture-pcm'


def test_no_speech_never_starts_a_summary_server_and_failed_prepare_retains_transcript():
    editor = NS(prepare=lambda **options: pytest.fail('No-speech input must not start the summary model'))
    processor = LocalMeetingProcessor(None, None, editor, None)
    assert processor.summarize(MeetingTranscript((), (), True, 1.), cancelled=lambda: False).reason == 'no_speech'
    editor.prepare = lambda **options: 'unavailable'
    transcript = NS(utterances=('public fixture',))
    assert processor.summarize(transcript, cancelled=lambda: False) == SummaryReply(None, 'unavailable')
