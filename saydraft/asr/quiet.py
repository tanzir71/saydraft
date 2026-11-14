"""One front-end pass before primary, routed fallback and explicit ASR retry."""

import time

from saydraft.audio.quiet import QuietSpeechProcessor, QuietSpeechSettings


class QuietSpeechAsr:
    def __init__(self, engine, settings, *, processor=None, clock=time.perf_counter):
        self.engine, self.settings = engine, settings
        self.processor = processor or QuietSpeechProcessor(settings)
        self.clock = clock
        self.last_timings = {}

    def __getattr__(self, name):
        method = getattr(self.engine, name)
        if name in ('retry_with_model', 'retry_with_all_languages'):
            return lambda audio, *args, **kwargs: self._transcribe(method, audio, *args, **kwargs)
        if name == 'with_language':
            return lambda language: QuietSpeechAsr(method(language), self.settings)
        return method

    def prepare(self):
        self.processor.prepare()
        prepare = getattr(self.engine, 'prepare', None)
        if prepare is not None:
            prepare()

    def transcribe(self, audio):
        return self._transcribe(self.engine.transcribe, audio)

    def _transcribe(self, method, audio, *args, **kwargs):
        self.last_timings = {}
        started = self.clock()
        try:
            processed = self.processor.process(audio)
        finally:
            self.last_timings['audio'] = max(0, self.clock() - started)
        budget = getattr(self.engine, 'set_audio_frontend_seconds', None)
        if budget is not None:
            budget(self.last_timings['audio'])
        try:
            return method(processed, *args, **kwargs)
        finally:
            self.last_timings.update(getattr(self.engine, 'last_timings', {}))

    def close(self):
        self.processor.close()
        close = getattr(self.engine, 'close', None)
        if close is not None:
            close()


def with_quiet_speech(engine, config):
    settings = QuietSpeechSettings.from_config(config)
    return QuietSpeechAsr(engine, settings) if settings.enabled else engine
