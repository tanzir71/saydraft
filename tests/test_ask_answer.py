"""Ask answers use independent owned Notes and explicit memory-clipboard Copy."""

import uuid

from saydraft.core.ask import AskResult
from saydraft.ui.ask_answer import AskAnswerWindow
from tests import test_command_recovery
from tests.test_scratchpad import settle

recovery = test_command_recovery.recovery


def test_answer_saves_separately_without_changing_active_note_or_clipboard(recovery):
    f = recovery
    f.group.window_factory = AskAnswerWindow
    primary = f.store.save(uuid.uuid4().hex, 'Primary public note')
    text = 'Public answer العربية বাংলা <b>literal</b>'
    first = f.group.present(AskResult(text, 'ok', 1))
    second = f.group.present(AskResult('Second answer', 'history_unavailable'))
    settle(f.qt, lambda: all(not window.draft.snapshot().dirty and not window.draft.snapshot().saving
                            for window in f.group.windows))
    assert f.store.active() == primary and len(f.store.list()) == 3
    assert first.editor.toPlainText() == text and first.windowTitle() == 'Ask answer — Saydraft'
    assert 'History could not save' in second.description.text()
    assert first.draft.snapshot().identifier != second.draft.snapshot().identifier
    assert not f.clipboard.texts
    first.copy_button.click()
    assert f.clipboard.texts == [text]


def test_retired_answer_does_not_create_a_note_or_steal_focus(recovery):
    f = recovery
    active = [True]
    def create(*args, **kwargs):
        window = AskAnswerWindow(*args, **kwargs)
        active[0] = False
        return window
    f.group.window_factory = create
    assert f.group.present(AskResult('Retired answer', 'ok', 1), valid=lambda: active[0]) is None
    assert not f.store.list() and not f.clipboard.texts and not f.group.windows
