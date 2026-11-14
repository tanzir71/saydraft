"""Plain, bounded settings passed only to an explicitly started capture helper."""

from dataclasses import dataclass, field
import json

from saydraft.audio.devices import InputSelection

MAX_SECONDS = 7200


def strict_json(text):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate meeting field')
            result[key] = value
        return result
    def constant(_value):
        raise ValueError('Invalid meeting numeric value')
    if type(text) is not str or len(text) > 8192:
        raise ValueError('Invalid meeting metadata')
    try:
        return json.loads(text, object_pairs_hook=unique, parse_constant=constant)
    except (TypeError, ValueError, RecursionError) as error:
        raise ValueError('Invalid meeting metadata') from error


def _device_text(value, limit):
    if type(value) is not str or len(value) > limit or any(ord(char) < 32 for char in value):
        raise ValueError('Invalid meeting device selection')
    try:
        value.encode('utf-8')
    except UnicodeError as error:
        raise ValueError('Invalid meeting device selection') from error


@dataclass(frozen=True)
class CaptureRequest:
    consent: bool = False
    microphone: InputSelection = field(default_factory=InputSelection)
    desktop_endpoint: str = ''
    max_seconds: int = MAX_SECONDS

    def __post_init__(self):
        if (type(self.consent) is not bool or type(self.microphone) is not InputSelection
                or type(self.max_seconds) is not int or not 1 <= self.max_seconds <= MAX_SECONDS):
            raise ValueError('Invalid meeting capture request')
        _device_text(self.desktop_endpoint, 1024)
        _device_text(self.microphone.name, 512)
        _device_text(self.microphone.hostapi, 512)

    def to_json(self):
        if not self.consent:
            raise PermissionError('Meeting recording needs explicit participant-consent confirmation')
        text = json.dumps({'consent': True, 'microphone': {'name': self.microphone.name,
            'hostapi': self.microphone.hostapi}, 'desktop_endpoint': self.desktop_endpoint,
            'max_seconds': self.max_seconds}, ensure_ascii=True, allow_nan=False)
        if len(text) > 8192:
            raise ValueError('Meeting device selections exceed the transport limit')
        return text

    @classmethod
    def from_json(cls, text):
        value = strict_json(text)
        if type(value) is not dict or set(value) != {'consent', 'microphone', 'desktop_endpoint', 'max_seconds'}:
            raise ValueError('Invalid meeting capture request')
        microphone = value['microphone']
        if type(microphone) is not dict or set(microphone) != {'name', 'hostapi'}:
            raise ValueError('Invalid meeting microphone selection')
        request = cls(value['consent'], InputSelection(**microphone), value['desktop_endpoint'], value['max_seconds'])
        if not request.consent:
            raise PermissionError('Meeting recording needs explicit participant-consent confirmation')
        return request
