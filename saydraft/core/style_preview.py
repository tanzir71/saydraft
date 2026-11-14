"""Private, bounded previews through the real processor with simulated delivery."""

from dataclasses import dataclass, replace
from types import SimpleNamespace

from saydraft.dictation import DictationConfig, DictationContext, DictationPipeline
from saydraft.dictation.glossary import Glossary
from saydraft.insert.inserter import InsertionResult
from .interfaces import TargetContext
from .processing import IdentityFormatter, TranscriptProcessor

MAX_PREVIEW = 4096


@dataclass(frozen=True)
class StylePreviewRequest:
    generation: int
    text: str
    context: DictationContext
    glossary: Glossary = Glossary()
    snippets: tuple[tuple[str, str], ...] = ()
    drop_message_period: bool = True
    voice_enter_enabled: bool = False
    model_settings: str = ""

    def key(self):
        return (self.text, self.context, self.glossary, self.snippets,
            self.drop_message_period, self.voice_enter_enabled, self.model_settings)


@dataclass(frozen=True)
class StylePreviewResult:
    request: StylePreviewRequest
    text: str = ""
    decision: str = "unavailable"
    enter_requested: bool = False


def render_style_preview(request, *, llm=None, deadline=None):
    if not isinstance(request.text, str) or not request.text or len(request.text) > MAX_PREVIEW:
        return StylePreviewResult(request, decision="invalid")
    pipeline = DictationPipeline(DictationConfig(drop_message_period=request.drop_message_period), llm_cleaner=llm)
    pipeline.glossary = request.glossary
    processor = TranscriptProcessor(cleaner=pipeline, formatter=IdentityFormatter(),
        history=SimpleNamespace(append=lambda entry: 1),
        inserter=SimpleNamespace(insert_text=lambda text, **kw:
            InsertionResult("inserted", "preview", enter_sent=kw.get("send_enter", False))),
        snippets=dict(request.snippets), voice_enter_enabled=request.voice_enter_enabled,
        reporter=SimpleNamespace(report=lambda *args: None))
    result = processor.process(request.text, context=replace(request.context, cleanup_deadline=deadline,
        translation_target=""),
        target=TargetContext("style-preview", request.context.app_title, app_group=request.context.app_group),
        model="preview", language=request.context.language)
    return StylePreviewResult(request, result.cleaned_text, pipeline.last_llm_decision, result.insertion.enter_sent)
