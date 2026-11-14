from contextlib import contextmanager
from types import SimpleNamespace as NS

import pytest

from saydraft.audio.devices import InputDevice, InputSelection
from saydraft.meetings.devices import MeetingDevices, MeetingOutput, discover_meeting_devices


def test_explicit_metadata_discovery_excludes_ambiguous_mics_and_matches_exact_output_ids():
    calls = []
    @contextmanager
    def com():
        calls.append('enter')
        yield
        calls.append('exit')
    backend = NS(all_speakers=lambda: [NS(id='one', name='Speakers'), NS(id='two', name='Speakers'),
        NS(id='missing', name='Unavailable'), NS(id='duplicate', name='Ambiguous'), NS(id='duplicate', name='Other')],
        all_microphones=lambda **options: calls.append(options) or [
            NS(id='one', isloopback=True, channels=2), NS(id='two', isloopback=True, channels=1)])
    inputs = [InputDevice(1, InputSelection('USB', 'WASAPI')), InputDevice(2, InputSelection('usb', 'wasapi')),
              InputDevice(3, InputSelection('Headset', 'WASAPI'))]
    result = discover_meeting_devices(input_provider=lambda: inputs, desktop_backend=backend, com_context=com)
    assert result.microphones == (inputs[2].selection,)
    assert [(item.endpoint_id, item.supported) for item in result.outputs] == [('one', True), ('two', False), ('missing', False)]
    assert calls == ['enter', {'include_loopback': True}, 'exit']


@pytest.mark.parametrize('channels,supported', [(0, False), (1, False), (2, True), (32, True), (33, False), (64, False)])
def test_loopback_channel_support_is_explicit(channels, supported):
    assert MeetingOutput('id', 'Speakers', channels).supported is supported


@pytest.mark.parametrize('endpoint,name,channels', [('', 'Speaker', 2), ('id\n', 'Speaker', 2),
    ('id', '', 2), ('id', 'Speaker', True), ('id', 'Speaker', 65), ('\ud800', 'Speaker', 2)])
def test_invalid_native_endpoint_metadata_fails_closed(endpoint, name, channels):
    with pytest.raises((ValueError, UnicodeError)):
        MeetingOutput(endpoint, name, channels)


def test_inventory_rejects_default_or_duplicate_devices():
    mic = InputSelection('Mic', 'WASAPI')
    output = MeetingOutput('one', 'Speakers', 2)
    for microphones, outputs in [((InputSelection(),), (output,)), ((mic, mic), (output,)), ((mic,), (output, output))]:
        with pytest.raises(ValueError):
            MeetingDevices(microphones, outputs)
