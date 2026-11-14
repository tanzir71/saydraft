import json
from types import SimpleNamespace as NS

import numpy as np

from saydraft.audio.quiet import QuietSpeechSettings
from saydraft.asr.quiet import QuietSpeechAsr
from tests.test_session_worker import Recorder, make_worker


def test_worker_retains_raw_capture_before_quiet_frontend_and_saves_history_before_memory_delivery():
    original = np.sin(np.arange(16000, dtype=np.float32) * 0.01) * 0.002
    class FixtureRecorder(Recorder):
        sample_rate = 16000
        def stop(self):
            self.stopped += 1
            return original.copy()
    recorder = FixtureRecorder()
    worker, clock, executor, events, _signals, _keyboard = make_worker(queued=True, recorder=recorder)
    received, retained = [], []
    def transcribe(audio):
        received.append(audio.copy())
        return 'quiet public words'
    engine = NS(transcribe=transcribe, prepare=lambda: None, last_language='en', last_timings={'stt': 0.1})
    worker.services.asr = QuietSpeechAsr(engine, QuietSpeechSettings(True, 6, False, False))
    worker.services.config['recording'].update(retain_audio=True, whisper_mode=True,
        whisper_gain_db=6, whisper_agc=False, whisper_enhancement=False)
    worker.services.audio_store = NS(save=lambda audio, rate: retained.append((audio.copy(), rate)) or 'owned-fixture.wav')
    try:
        assert worker.start_recording()
        executor.drain()
        clock.now = 1
        worker.stop_recording()
        executor.drain()
        assert len(retained) == len(received) == 1 and retained[0][1] == 16000
        np.testing.assert_array_equal(retained[0][0], original)
        np.testing.assert_allclose(received[0], original * 10 ** (6 / 20), rtol=1e-6)
        assert [event[0] for event in events] == ['history', 'insert']
        entry = events[0][1]
        assert entry.raw_text == 'quiet public words' and entry.audio_path == 'owned-fixture.wav'
        assert json.loads(entry.timings_json)['audio'] >= 0
    finally:
        worker.shutdown()


def test_practice_reuses_asr_only_when_quiet_settings_also_match(monkeypatch):
    import copy
    worker, _clock, _executor, _events, _signals, _keyboard = make_worker()
    snapshot = copy.deepcopy(worker.services.config)
    sentinel = object()
    calls = []
    monkeypatch.setattr('saydraft.asr.selection.create_asr', lambda config: calls.append(config) or sentinel)
    try:
        assert worker._practice_asr(snapshot) is worker.services.asr
        snapshot['recording']['whisper_mode'] = True
        assert worker._practice_asr(snapshot) is sentinel and calls == [snapshot]
    finally:
        worker.shutdown()
