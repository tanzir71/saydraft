"""Meeting-only multilingual retry, without dictation's release latency budget."""

import copy

from saydraft.asr.languages import PARAKEET_LANGUAGES
from saydraft.asr.router import ALL_LANGUAGES, choose_route, low_confidence_reason
from saydraft.asr.selection import configured_model_id


def speech_models(config):
    stt = config['stt']
    if not stt.get('routing_enabled', False):
        return (configured_model_id(config),)
    route = choose_route(stt.get('pinned_languages', ()), english_max=stt.get('english_max', False))
    # Auto needs the shared multilingual model ready before recording, because
    # the language of a later chunk is not known during setup. Pins/manual
    # choices retain their selected model and do not acquire language packs.
    return (route.model_id, ALL_LANGUAGES) if route.reason == 'auto' else (route.model_id,)


class MeetingAutoAsr:
    def __init__(self, primary, *, resolver=None):
        self.primary, self.resolver = primary, resolver
        self.model_id = primary.model_id
        self.last_language = None
        self.last_timings = {}

    def prepare(self):
        if self.resolver is None:
            from saydraft.model_download import find_installed_model
            resolve = find_installed_model
        else:
            resolve = self.resolver
        if resolve(ALL_LANGUAGES, check_hashes=True) is None:
            raise FileNotFoundError('Review and download the shared All languages model for meeting Auto first')
        self.primary.prepare()

    def transcribe(self, audio):
        text = self.primary.transcribe(audio)
        language = self.primary.last_language
        if self.primary.model_id != ALL_LANGUAGES and (language not in PARAKEET_LANGUAGES
                or low_confidence_reason(text, len(audio) / 16000, language) is not None):
            # A failed retry is a recognition failure, not permission to label
            # unsupported-language Parakeet text as a successful transcript.
            text = self.primary.retry_with_model(audio, ALL_LANGUAGES)
        self.model_id = self.primary.model_id
        self.last_language = self.primary.last_language
        self.last_timings = dict(getattr(self.primary, 'last_timings', {}))
        return text


def create_meeting_asr(config):
    from saydraft.asr.selection import create_asr
    snapshot = copy.deepcopy(config)
    stt = snapshot['stt']
    stt['app_model_overrides'] = []  # A meeting has no foreground-app context.
    asr = create_asr(snapshot)
    return MeetingAutoAsr(asr) if stt.get('routing_enabled', False) and not stt.get('pinned_languages') else asr
