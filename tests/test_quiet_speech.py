from types import SimpleNamespace as NS

import numpy as np
import pytest

from saydraft.audio.gtcrn import GtcrnDenoiser
from saydraft.audio.quiet import QuietSpeechProcessor, QuietSpeechSettings, gain_and_agc, vad_settings
from saydraft.asr.quiet import QuietSpeechAsr, with_quiet_speech
from saydraft.config import default_config, sanitize_config


def quiet_config(**settings):
    config = default_config()
    config['recording'].update(whisper_mode=True, whisper_enhancement=False, **settings)
    return config


def test_disabled_mode_preserves_identity_and_imports_or_prepares_nothing():
    source = np.array([0.01, -0.1], dtype=np.float32)
    engine = NS()
    def forbidden():
        raise AssertionError('Disabled Whisper mode cannot load a denoiser')
    processor = QuietSpeechProcessor(QuietSpeechSettings(), denoiser_factory=forbidden)
    processor.prepare()
    assert processor.process(source) is source
    assert with_quiet_speech(engine, default_config()) is engine


@pytest.mark.parametrize('n', [0, 1, 319, 320, 321, 16001])
def test_gain_without_agc_has_exact_sample_coverage_and_preserves_source(n):
    audio = np.linspace(-0.01, 0.01, n, dtype=np.float32)
    original = audio.copy()
    settings = QuietSpeechSettings(True, 6, False, False)
    result = gain_and_agc(audio, settings)
    np.testing.assert_array_equal(audio, original)
    np.testing.assert_allclose(result, original * 10 ** (6 / 20), rtol=1e-6)
    assert result.shape == audio.shape and result.dtype == np.float32


def test_agc_raises_quiet_speech_without_pumping_silence_or_clipping_peaks():
    time = np.arange(32000, dtype=np.float32)
    audio = np.sin(time * 0.1) * 0.001
    output = gain_and_agc(audio, QuietSpeechSettings(True, 12, True, False))
    assert np.sqrt(np.mean(output[-8000:] ** 2)) > 10 * np.sqrt(np.mean(audio[-8000:] ** 2))
    silence = np.zeros(16001, dtype=np.float32)
    np.testing.assert_array_equal(gain_and_agc(silence, QuietSpeechSettings(True)), silence)
    loud = np.concatenate((audio, np.array([1, -1] * 500, dtype=np.float32)))
    result = gain_and_agc(loud, QuietSpeechSettings(True, 24, True, False))
    assert np.isfinite(result).all() and np.max(np.abs(result)) <= 0.980001


@pytest.mark.parametrize('gain', [float('nan'), float('inf'), -1, 24.1, True, None])
def test_invalid_gain_is_rejected_and_config_sanitizes_it(gain):
    with pytest.raises(ValueError):
        QuietSpeechSettings(True, gain)
    config = default_config()
    config['recording']['whisper_gain_db'] = gain
    actual = sanitize_config(config)['recording']['whisper_gain_db']
    assert np.isfinite(actual) and 0 <= actual <= 24


@pytest.mark.parametrize('audio', [np.array([float('nan')]), np.array([float('inf')]), np.zeros((2, 2))])
def test_invalid_audio_declines_processing_without_repairing_or_modifying_it(audio):
    original = audio.copy()
    with pytest.raises(ValueError):
        gain_and_agc(audio, QuietSpeechSettings(True))
    np.testing.assert_array_equal(audio, original)


def test_denoiser_is_lazy_reused_and_validates_shape_without_changing_original():
    calls = []
    def factory():
        calls.append('prepare')
        return lambda audio: calls.append(audio.copy()) or audio * 0.5
    processor = QuietSpeechProcessor(QuietSpeechSettings(True, 0, False, True), denoiser_factory=factory)
    audio = np.array([0.01, -0.02], dtype=np.float32)
    assert calls == []
    processor.prepare()
    for _ in range(2):
        np.testing.assert_allclose(processor.process(audio), audio * 0.5)
    assert calls[0] == 'prepare' and len(calls) == 3
    np.testing.assert_array_equal(audio, [np.float32(0.01), np.float32(-0.02)])
    processor.close()
    processor.prepare()
    assert calls[-1] == 'prepare'


@pytest.mark.parametrize('output', [np.ones(2), np.array([float('nan')]), np.zeros((1, 1))])
def test_invalid_enhancement_output_never_reaches_asr(output):
    processor = QuietSpeechProcessor(QuietSpeechSettings(True), denoiser_factory=lambda: lambda audio: output)
    with pytest.raises(ValueError):
        processor.process(np.array([0.01], dtype=np.float32))


def test_vad_profile_is_shared_preserves_off_settings_and_respects_explicit_sensitive_settings():
    from saydraft.asr.sherpa_parakeet import ParakeetConfig
    from saydraft.stt.whisper_engine import WhisperEngineConfig
    config = default_config()
    baseline = vad_settings(config)
    assert baseline['vad_energy_threshold'] == 0.003 and baseline['silero_threshold'] == 0.5
    config['recording']['whisper_mode'] = True
    for cls in (ParakeetConfig, WhisperEngineConfig):
        values = cls.from_app_config(config)
        assert values.vad_energy_threshold == 0.00075 and values.silero_threshold == 0.35
        assert values.silence_padding_ms == 200 and values.vad_aggressiveness == 1
    config['stt'].update(vad_energy_threshold=0.0001, vad_aggressiveness=0, silence_padding_ms=350, silence_trim=False)
    values = vad_settings(config)
    assert values['vad_energy_threshold'] == 0.0001 and values['vad_aggressiveness'] == 0
    assert values['silence_padding_ms'] == 350 and not values['silence_trim']


@pytest.fixture
def native_stub(tmp_path, monkeypatch):
    monkeypatch.setattr('saydraft.models.downloader.installation_ready', lambda *args, **kwargs: True)
    calls = []
    def denoise(audio, sample_rate):
        assert len(audio) >= 512 and len(audio) % 256 == 0
        assert sample_rate == 16000
        calls.append(audio.copy())
        # Match the native API's output rounding rather than pretending it keeps tails.
        return NS(samples=audio[:len(audio) // 256 * 256].copy(), sample_rate=16000)
    engine = GtcrnDenoiser(tmp_path, factory=lambda path: denoise)
    return engine, calls


@pytest.mark.parametrize('n', [0, 1, 511, 512, 513, 1000, 16001, 400001, 900513])
def test_gtcrn_padding_bounded_windows_and_context_retain_every_original_sample(native_stub, n):
    engine, calls = native_stub
    audio = np.sin(np.arange(n, dtype=np.float32) * 0.01) * 0.02
    result = engine(audio)
    np.testing.assert_array_equal(result, audio)
    assert all(len(call) <= 400000 + 16000 + 512 + 255 for call in calls)
    assert (len(calls) == 0) == (n == 0)


def test_gtcrn_changed_installation_is_refused_before_native_work(native_stub, monkeypatch):
    engine, calls = native_stub
    monkeypatch.setattr('saydraft.models.downloader.installation_ready', lambda *args, **kwargs: False)
    with pytest.raises(ValueError, match='changed'):
        engine(np.ones(513, dtype=np.float32))
    assert calls == []


def test_wrapper_processes_primary_and_explicit_retry_once_and_forwards_metadata():
    events = []
    class Engine:
        model_id = 'public-model'
        last_language = 'en'
        last_timings = {'stt': 0.2}
        def transcribe(self, audio):
            events.append(('primary', audio.copy()))
            return 'public words'
        def retry_with_model(self, audio, model):
            events.append((model, audio.copy()))
            return 'retried words'
        def set_audio_frontend_seconds(self, seconds):
            self.budget = seconds
    count = []
    processor = NS(process=lambda audio: count.append(1) or audio * 2)
    ticks = iter([0, 0.04, 1, 1.05])
    engine = Engine()
    wrapped = QuietSpeechAsr(engine, QuietSpeechSettings(True), processor=processor, clock=lambda: next(ticks))
    audio = np.array([0.01], dtype=np.float32)
    assert wrapped.transcribe(audio) == 'public words'
    assert wrapped.last_timings == {'stt': 0.2, 'audio': 0.04}
    assert wrapped.retry_with_model(audio, 'other-model') == 'retried words'
    assert len(count) == 2 and engine.budget == pytest.approx(0.05)
    assert wrapped.model_id == 'public-model' and wrapped.last_language == 'en'
    for _, received in events:
        np.testing.assert_array_equal(received, audio * 2)
    assert not hasattr(QuietSpeechAsr(NS(), QuietSpeechSettings(True)), 'retry_with_model')


def test_prepare_frontend_failure_prevents_native_asr_preparation():
    calls = []
    def fail():
        raise FileNotFoundError('Set up speech enhancement')
    wrapped = QuietSpeechAsr(NS(prepare=lambda: calls.append('asr')), QuietSpeechSettings(True),
        processor=NS(prepare=fail))
    with pytest.raises(FileNotFoundError):
        wrapped.prepare()
    assert calls == []


def test_create_asr_has_one_wrapper_for_router_and_plain_engines(monkeypatch):
    from saydraft.asr.selection import create_asr
    from saydraft.core.interfaces import TargetContext
    config = quiet_config(whisper_gain_db=6, whisper_agc=False)
    config['stt']['pinned_languages'] = ['en']
    received = []
    class Engine:
        model_id = 'parakeet-tdt-0-6b-v3-int8'
        last_language = 'en'
        last_timings = {}
        def transcribe(self, audio):
            received.append(audio.copy())
            return 'recognized text'
    monkeypatch.setattr('saydraft.asr.sherpa_parakeet.ParakeetEngine', lambda cfg: Engine())
    wrapped = create_asr(config)
    assert isinstance(wrapped, QuietSpeechAsr)
    wrapped.set_context(TargetContext(app_group='general'))
    audio = np.full(1600, 0.01, dtype=np.float32)
    assert wrapped.transcribe(audio) == 'recognized text'
    np.testing.assert_allclose(received[0], audio * 10 ** (6 / 20), rtol=1e-6)
    assert not isinstance(wrapped.engine._engine(wrapped.engine._route), QuietSpeechAsr)
    config['stt']['routing_enabled'] = False
    assert isinstance(create_asr(config), QuietSpeechAsr)
    assert isinstance(create_asr(config, preprocess=False), Engine)


def test_quiet_mode_keeps_live_preview_but_cannot_bypass_enhanced_primary_with_streaming_text():
    from saydraft.core.preview import preview_eligibility, streaming_result_enabled
    config = quiet_config()
    config['app']['tier'] = 'pro'
    config['labs'].update(live_preview=True, use_streaming_result=True)
    assert preview_eligibility(config, None) is None
    assert not streaming_result_enabled(config)
    config['recording']['whisper_mode'] = False
    assert streaming_result_enabled(config)


def test_meeting_setup_reviews_enhancement_when_its_recognition_uses_quiet_mode():
    from saydraft.audio.gtcrn import MODEL_ID
    from saydraft.meetings.setup import meeting_setup_plan
    config = quiet_config()
    config['app']['tier'] = 'pro'
    without = meeting_setup_plan(config)
    assert MODEL_ID not in without.model_ids
    config['recording']['whisper_enhancement'] = True
    reviewed = meeting_setup_plan(config)
    assert MODEL_ID in reviewed.model_ids
    assert reviewed.download_bytes - without.download_bytes == 535638  # Notices are bundled.


def test_package_smoke_modes_are_exclusive_before_any_runtime_or_firewall_action(tmp_path, monkeypatch):
    from saydraft import package_check
    calls = []
    monkeypatch.setattr(package_check, 'verify_runtime', lambda: calls.append('runtime'))
    with pytest.raises(SystemExit):
        package_check.main([str(tmp_path / 'report.json'), '--enhancement-smoke', str(tmp_path / 'model'),
            '--firewall-smoke', str(tmp_path / 'speech')])
    assert calls == [] and not (tmp_path / 'report.json').exists()


def test_selected_enhancement_version_is_protected_from_model_storage_removal(tmp_path, monkeypatch):
    from saydraft.audio.gtcrn import MODEL_ID
    from saydraft.models import storage
    from saydraft.models.layout import model_relative_dir
    from saydraft.models.manifest import get_model
    monkeypatch.setattr(storage, 'storage_roots', lambda: (storage.StorageRoot(tmp_path, 'QA', True),))
    config = quiet_config()
    selected = (tmp_path / model_relative_dir(get_model(MODEL_ID))).resolve()
    assert selected not in storage.protected_paths(config)
    config['recording']['whisper_enhancement'] = True
    assert selected in storage.protected_paths(config)
