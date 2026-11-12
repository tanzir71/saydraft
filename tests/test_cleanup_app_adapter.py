import time
from types import SimpleNamespace

import pytest

from saydraft.cleanup.llm.sidecar import SidecarReply
from saydraft.core.interfaces import TargetContext
from saydraft.core.processing import IdentityFormatter, TranscriptProcessor
from saydraft.dictation import DictationConfig, DictationContext, DictationPipeline
from saydraft.dictation.glossary import Glossary
from saydraft.dictation.llm_local import LocalLLMConfig, LocalLLMCleaner
from saydraft.history import DictationHistoryStore
from saydraft.insert.inserter import InsertionResult
from tests.test_cleanup_streaming import DONE, FakeModel, frame


@pytest.mark.parametrize("chunks,decision,expected", [
    ([frame("Send 2 files to ⟦T0⟧.", finish="stop"), DONE], "accepted", "Send 2 files to Saydraft."),
    ([frame("Send 3 files to ⟦T0⟧.", finish="stop"), DONE], "rejected:numbers_changed", "Send 2 files to Saydraft"),
    ([frame("Send 2 files.", finish="stop"), DONE], "protected_changed", "Send 2 files to Saydraft"),
    ([frame("Send 2 files to ⟦T0⟧.")], "incomplete", "Send 2 files to Saydraft"),
])
def test_owned_stream_adapter_validates_and_restores_before_history_and_insertion(tmp_path, chunks, decision, expected):
    model = FakeModel(chunks)
    closed = []
    manager = SimpleNamespace(
        run=lambda operation, *, timeout: SidecarReply(operation(model, time.monotonic() + timeout), "ok"),
        warm=lambda: True, close=lambda: closed.append(True))
    cfg = LocalLLMConfig(enabled=True, model_path=str(tmp_path / "fixture.gguf"), prepare_prompt=False)
    cleaner = DictationPipeline(DictationConfig(llm=cfg), llm_cleaner=LocalLLMCleaner(
        cfg, manager_factory=lambda config: manager))
    cleaner.glossary = Glossary(user_terms=("Saydraft",))
    history = DictationHistoryStore(tmp_path / "history.db")
    inserted = []

    def insert(text, **kwargs):
        rows = history.list_recent()
        assert len(rows) == 1 and rows[0].cleaned_text == text
        inserted.append(text)
        return InsertionResult("inserted", "fixture")

    processor = TranscriptProcessor(cleaner=cleaner, formatter=IdentityFormatter(), history=history,
                                    inserter=SimpleNamespace(insert_text=insert))
    result = processor.process("um send 2 files to Saydraft", target=TargetContext("fixture", "Mail", app_group="email"),
        context=DictationContext(), model="fixture", language="en")
    assert result.cleaned_text == expected and inserted == [expected]
    row = history.list_recent()[0]
    assert row.raw_text == "um send 2 files to Saydraft" and row.llm_decision == decision
    final_prompt = model.requests[1][1]["payload"]["messages"][-1]["content"]
    assert 'app: "Mail"' in final_prompt and 'group: "email"' in final_prompt and 'lang: "en"' in final_prompt
    cleaner.close()
    assert closed == [True]
