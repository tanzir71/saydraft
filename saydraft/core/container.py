"""Construct application services once; the worker receives replaceable ports."""

from __future__ import annotations

from dataclasses import dataclass

from .interfaces import AsrEngine, AudioCapture, Cleaner, ContextProvider, Formatter, HistoryStore, Inserter, PreviewModel
from .processing import IdentityFormatter, TranscriptProcessor
from .preferences import read_profiles, read_snippets
from .timings import TimingReporter


@dataclass
class Services:
    config: dict
    recorder: AudioCapture
    asr: AsrEngine
    cleaner: Cleaner
    formatter: Formatter
    inserter: Inserter
    context: ContextProvider
    history: HistoryStore
    processor: TranscriptProcessor
    profiles: list[dict]
    audio_store: object | None = None
    retry_asr: AsrEngine | None = None
    preview: PreviewModel | None = None


def create_services(config: dict, *, level_callback=None, notify=lambda message: None) -> Services:
    from saydraft.audio.recorder import AudioRecorder
    from saydraft.dictation import DictationConfig, DictationPipeline
    from saydraft.dictation.llm_local import LocalLLMConfig
    from saydraft.history import DictationHistoryStore
    from saydraft.insert.inserter import Inserter as ClipboardInserter
    from saydraft.paths import resolve_data_path
    from saydraft.asr.selection import create_asr
    from saydraft.asr.retry import AllLanguagesRetry
    from saydraft.data.audio import AudioStore
    from .context import ForegroundContextProvider

    profiles = read_profiles(resolve_data_path(config["dictation"]["app_profiles_path"]))
    llm = dict(config["llm"])
    cleaner = DictationPipeline(DictationConfig(
        glossary_path=str(resolve_data_path(config["dictation"]["glossary_path"])),
        drop_message_period=config["dictation"].get("drop_message_period", True),
        llm=LocalLLMConfig(
            enabled=llm["enabled"], model_path=str(resolve_data_path(llm["model_path"])),
            n_ctx=llm["n_ctx"], max_tokens=llm["max_tokens"], temperature=llm["temperature"],
            top_p=llm["top_p"], n_threads=llm["threads"], n_gpu_layers=llm["gpu_layers"],
            backend=llm.get("backend", "cpu"), timeout_ms=llm.get("timeout_ms", 800),
            idle_seconds=llm.get("idle_seconds", 900),
        ),
    ))
    recorder = AudioRecorder(max_seconds=config["recording"]["max_seconds"], level_callback=level_callback)
    asr = create_asr(config)
    context = ForegroundContextProvider()
    inserter = ClipboardInserter(focus_provider=lambda: context.capture().focus, profiles=profiles)
    snippets = read_snippets()
    history = DictationHistoryStore(import_paths={
        "glossary": resolve_data_path(config["dictation"]["glossary_path"]),
        "profiles": resolve_data_path(config["dictation"]["app_profiles_path"]),
        "snippets": resolve_data_path("snippets.txt"),
    })
    formatter = IdentityFormatter()
    processor = TranscriptProcessor(cleaner=cleaner, formatter=formatter, history=history,
                                    inserter=inserter, snippets=snippets, notify=notify,
                                    voice_enter_enabled=config["dictation"].get("voice_enter_enabled", False),
                                    reporter=TimingReporter(notify=notify, llm_enabled=llm["enabled"]))
    preview = None
    if config.get("labs", {}).get("live_preview", False):
        from .preview import preview_eligibility
        from saydraft.models.hardware import latest_report
        from saydraft.asr.sherpa_stream import NemotronPreviewModel

        if preview_eligibility(config, latest_report()) is None:
            preview = NemotronPreviewModel()
    return Services(config, recorder, asr, cleaner, formatter, inserter, context, history, processor, profiles,
                    AudioStore(history.db_path.parent / "audio"), AllLanguagesRetry(config, asr), preview)
