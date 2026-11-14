from dataclasses import replace
from types import SimpleNamespace as NS

import pytest
from PySide6 import QtCore, QtWidgets

from saydraft.core.meeting_controller import MeetingStatus
from saydraft.ui.meeting_capsule import MeetingCapsule

APP = None


@pytest.fixture
def capsule():
    global APP
    APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    clock = NS(now=100.)
    widget = MeetingCapsule(clock=lambda: clock.now)
    yield APP, widget, clock
    if widget.status is not None:
        widget.accept_status(replace(widget.status, phase='cancelled', capture_stopped=True))
    widget.close()
    widget.deleteLater()
    APP.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def pump(app):
    for _ in range(4):
        app.processEvents()


def test_acknowledgement_is_after_paint_and_only_for_the_current_visible_indicator(capsule):
    app, widget, _ = capsule
    ready = []
    widget.indicator_ready.connect(ready.append)
    status = MeetingStatus(object(), 'indicator', False)
    assert widget.accept_status(status)
    assert not ready
    pump(app)
    assert ready == [status] and widget.isVisible()
    widget.repaint()
    pump(app)
    assert ready == [status]


def test_cancelled_indicator_cannot_acknowledge_a_late_paint(capsule):
    app, widget, _ = capsule
    ready = []
    widget.indicator_ready.connect(ready.append)
    status = MeetingStatus(object(), 'indicator', False)
    widget.accept_status(status)
    widget.accept_status(replace(status, phase='cancelled', capture_stopped=True))
    pump(app)
    assert not ready


@pytest.mark.parametrize('phase', ['indicator', 'checking', 'preparing', 'recording', 'stopping', 'stop_unconfirmed'])
def test_recording_capsule_refuses_hide_close_and_invisibility_until_confirmed_stopped(capsule, phase):
    app, widget, _ = capsule
    stops = []
    widget.stop_requested.connect(lambda *args: stops.append(args))
    status = MeetingStatus(object(), phase, False)
    widget.accept_status(status)
    pump(app)
    widget.hide()
    widget.setVisible(False)
    widget.close()
    pump(app)
    assert widget.isVisible() and stops == [(status, False)]
    assert widget.heading.text() == 'Recording meeting'
    widget.accept_status(replace(status, phase='transcribing', capture_stopped=True))
    widget.close()
    pump(app)
    assert not widget.isVisible()


def test_stop_discard_retry_and_notes_controls_keep_the_original_status_ticket(capsule):
    _, widget, _ = capsule
    events = []
    widget.stop_requested.connect(lambda *args: events.append(('stop', *args)))
    widget.retry_requested.connect(lambda value: events.append(('retry', value)))
    widget.discard_requested.connect(lambda value: events.append(('discard', value)))
    widget.notes_requested.connect(lambda value: events.append(('notes', value)))
    status = MeetingStatus(object(), 'recording', False)
    widget.accept_status(status)
    widget.primary.click()
    widget.secondary.click()
    recovery = replace(status, phase='recovery', capture_stopped=True, retained='text')
    widget.accept_status(recovery)
    widget.primary.click()
    widget.secondary.click()
    finished = replace(status, phase='finished', capture_stopped=True, reason='ok', note_id='a' * 32)
    widget.accept_status(finished)
    widget.primary.click()
    assert events == [('stop', status, False), ('stop', status, True), ('retry', recovery),
                      ('discard', recovery), ('notes', finished)]


def test_recording_duration_starts_at_capture_preparation_and_resets_for_new_meeting(capsule):
    _, widget, clock = capsule
    status = MeetingStatus(object(), 'checking', False)
    widget.accept_status(status)
    clock.now += 65
    widget._elapsed()
    assert widget.elapsed.isHidden()
    widget.accept_status(replace(status, phase='preparing'))
    clock.now += 65
    widget._elapsed()
    assert widget.elapsed.text() == '01:05'
    widget.accept_status(MeetingStatus(object(), 'preparing', False))
    assert widget.elapsed.text() == '00:00'


@pytest.mark.parametrize('retained,expected', [('audio', 'Audio is kept in memory'), ('text', 'unsaved text')])
def test_recovery_explains_what_is_retained_without_claiming_audio_is_saved(capsule, retained, expected):
    _, widget, _ = capsule
    widget.accept_status(MeetingStatus(object(), 'recovery', True, retained=retained))
    assert expected in widget.description.text() and widget.primary.text() == 'Retry'
    assert widget.description.textFormat() == QtCore.Qt.PlainText


def test_hiding_processing_is_respected_but_a_new_recording_or_recovery_is_visible(capsule):
    app, widget, _ = capsule
    status = MeetingStatus(object(), 'transcribing', True, progress=20)
    widget.accept_status(status)
    widget.close()
    widget.accept_status(replace(status, progress=30))
    pump(app)
    assert not widget.isVisible()
    widget.accept_status(replace(status, phase='recovery', retained='text'))
    assert widget.isVisible()
    widget.close()
    widget.accept_status(MeetingStatus(object(), 'indicator', False))
    assert widget.isVisible()


def test_cancel_processing_does_not_hide_a_recording_or_repeat_automatically(capsule):
    _, widget, _ = capsule
    stops = []
    widget.stop_requested.connect(lambda *args: stops.append(args))
    status = MeetingStatus(object(), 'summarizing', True)
    widget.accept_status(status)
    widget.primary.click()
    assert stops == [(status, True)] and not widget.primary.isEnabled()
    widget.primary.click()
    assert len(stops) == 1


def test_silence_terminal_state_does_not_offer_a_nonexistent_note(capsule):
    _, widget, _ = capsule
    requested = []
    widget.notes_requested.connect(requested.append)
    widget.accept_status(MeetingStatus(object(), 'empty', True, reason='no_speech'))
    assert 'no Note was saved' in widget.description.text() and widget.primary.text() == 'Close'
    widget.primary.click()
    assert not requested and not widget.isVisible()


def test_finished_no_speech_is_not_misrepresented_as_a_transcript(capsule):
    _, widget, _ = capsule
    widget.accept_status(MeetingStatus(object(), 'finished', True, reason='no_speech'))
    assert 'No speech was recognized' in widget.description.text()


def test_custom_translucent_window_paints_an_opaque_panel_behind_its_text(capsule):
    app, widget, _ = capsule
    widget.accept_status(MeetingStatus(object(), 'recording', False))
    pump(app)
    pixels = widget.grab().toImage()
    assert pixels.pixelColor(10, pixels.height() // 2).alpha() == 255
    assert pixels.pixelColor(pixels.width() // 2, 5).alpha() == 255
