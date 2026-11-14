"""Explicit read-only meeting endpoint discovery; no stream is opened here."""

from dataclasses import dataclass
from collections import Counter

from saydraft.audio.devices import InputSelection, list_inputs
from .audio import audio_com_context


@dataclass(frozen=True)
class MeetingOutput:
    endpoint_id: str
    name: str
    channels: int

    def __post_init__(self):
        for value, limit in ((self.endpoint_id, 1024), (self.name, 512)):
            if type(value) is not str or not value or len(value) > limit or any(ord(char) < 32 for char in value):
                raise ValueError('Invalid meeting output endpoint')
            value.encode('utf-8')
        if type(self.channels) is not int or not 0 <= self.channels <= 64:
            raise ValueError('Invalid meeting channel count')

    @property
    def supported(self):
        return 2 <= self.channels <= 32


@dataclass(frozen=True)
class MeetingDevices:
    microphones: tuple[InputSelection, ...]
    outputs: tuple[MeetingOutput, ...]

    def __post_init__(self):
        if (type(self.microphones) is not tuple or type(self.outputs) is not tuple
                or any(type(item) is not InputSelection or not item.name for item in self.microphones)
                or any(type(item) is not MeetingOutput for item in self.outputs)
                or len({item.key for item in self.microphones}) != len(self.microphones)
                or len({item.endpoint_id for item in self.outputs}) != len(self.outputs)):
            raise ValueError('Invalid meeting device inventory')


def _output_choices(backend):
    # Native device references die before the caller leaves its COM apartment.
    loops = tuple(backend.all_microphones(include_loopback=True))
    speakers = tuple(backend.all_speakers())
    identities = Counter(item.id for item in speakers)
    outputs = []
    for speaker in speakers:
        if identities[speaker.id] != 1:
            continue
        matches = [item for item in loops if item.id == speaker.id and item.isloopback is True]
        channels = matches[0].channels if len(matches) == 1 and type(matches[0].channels) is int else 0
        outputs.append(MeetingOutput(speaker.id, speaker.name, channels))
    return tuple(outputs)


def discover_meeting_devices(*, input_provider=list_inputs, desktop_backend=None, com_context=audio_com_context):
    """Call off the GUI thread only after the user's Refresh devices action."""
    inputs = tuple(input_provider())
    counts = Counter(item.selection.key for item in inputs)
    microphones = tuple(item.selection for item in inputs if counts[item.selection.key] == 1)
    with com_context():
        if desktop_backend is None:
            import soundcard
            desktop_backend = soundcard
        outputs = _output_choices(desktop_backend)
    return MeetingDevices(microphones, outputs)
