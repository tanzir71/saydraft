from types import SimpleNamespace

from saydraft.app import WorkerController
from saydraft.data.notes import NoteStore
from saydraft.ui.notes_page import NotesPage
from tests.test_history_window import qt_modules


def test_notes_button_and_hint_show_toggle_and_saving_states(tmp_path):
    qt = qt_modules()
    page = NotesPage(NoteStore(tmp_path / 'history.db'))
    requests = []
    page.record_requested.connect(lambda: requests.append(True))
    try:
        page.show()
        qt.QtWidgets.QApplication.processEvents()
        assert page.record_button.isVisible() and 'F10' in page.record_hint.text()
        page.record_button.click()
        page.accept_recording_status('recording')
        assert page.record_button.text() == 'Stop recording'
        page.record_button.click()
        assert requests == [True, True]
        page.accept_recording_status('saving')
        assert not page.record_button.isEnabled()
        page.record_button.click()
        assert len(requests) == 2
        page.accept_recording_status('idle')
        assert page.record_button.isEnabled() and page.record_button.text() == 'Record note'
        page.set_recording_shortcut('ctrl+alt+n')
        assert 'CTRL+ALT+N' in page.record_hint.text() and 'F10' not in page.record_hint.text()
    finally:
        page.jobs.close()
        page.close()
        page.deleteLater()
        qt.QtWidgets.QApplication.sendPostedEvents(None, qt.QtCore.QEvent.DeferredDelete)


def test_controller_routes_note_button_and_bar_stop_to_note_owner():
    calls = []
    controller = WorkerController(SimpleNamespace())
    controller.core = SimpleNamespace(record_note=lambda: calls.append('toggle') or True,
        note_recording_status=lambda: 'recording', stop_recording=lambda: calls.append('stop'),
        hotkeys=SimpleNamespace(_controller=SimpleNamespace(is_locked=False)))
    assert controller.record_note() and controller.is_hands_free()
    assert controller.request_bar_action(stop=True)
    assert calls == ['toggle', 'stop']
