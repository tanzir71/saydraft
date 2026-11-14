"""Prepare verified local meeting models; share the exclusive editing-model lease.

All methods run on an application worker. This processor has no capture,
clipboard or foreground port and never downloads. The ASR uses the app's saved
language/routing settings, without an app-context override or a source re-read.
"""

import gc

from .diarization import SpeakerDiarizer
from .summary import SummaryReply
from .transcription import MeetingTranscriber


class MeetingPreparationError(ValueError):
    pass


class LocalMeetingProcessor:
    def __init__(self, asr, diarizer, editor, store, *, detector_factory=None):
        self.asr, self.diarizer, self.editor, self.store = asr, diarizer, editor, store
        self.detector_factory = detector_factory

    def transcribe(self, audio, *, cancelled, on_progress):
        try:
            return MeetingTranscriber(self.asr, self.diarizer, detector_factory=self.detector_factory).transcribe(
                audio, cancelled=cancelled, on_progress=on_progress)
        finally:
            self.release_speech()

    def release_speech(self):
        # These engines belong only to this meeting, not ordinary dictation.
        self.asr = self.diarizer = None
        gc.collect()

    def summarize(self, transcript, *, cancelled):
        if not transcript.utterances:
            return SummaryReply(None, 'no_speech')
        reason = self.editor.prepare(cancelled=cancelled)
        if reason != 'ready':
            return SummaryReply(None, reason)
        return self.editor.summarize_meeting(transcript, cancelled=cancelled)

    def close(self):
        self.release_speech()
        self.editor.close()


def prepare_meeting(services, config, *, need_speech=True):
    from saydraft.asr.selection import create_asr
    from saydraft.data.notes import NoteStore
    from saydraft.models.command import installed_command_config, meeting_choice
    from saydraft.models.hardware import latest_report

    choice = meeting_choice(config, latest_report())
    if choice.reason != 'ready':
        raise MeetingPreparationError(choice.reason)
    sidecar = installed_command_config(choice, threads=config['llm'].get('threads') or 4)
    if sidecar is None:
        raise MeetingPreparationError('model_missing')
    factory = getattr(getattr(services.cleaner, 'llm', None), 'command_session', None)
    if not callable(factory):
        raise MeetingPreparationError('model_unavailable')
    # Retire normal cleanup warming before recording and reserve its existing
    # exclusive editing lease. The 4B server starts only after speech is freed.
    editor = factory(sidecar, choice.model_id)
    if editor is None:
        raise MeetingPreparationError('model_busy')
    processor = None
    try:
        processor = LocalMeetingProcessor(None, None, editor, NoteStore(services.history.db_path))
        if need_speech:
            processor.asr = create_asr(config)
            processor.asr.prepare()
            processor.diarizer = SpeakerDiarizer()
            processor.diarizer.prepare()
        return processor
    except BaseException:
        if processor is not None:
            processor.close()
        else:
            editor.close()
        raise
