"""Stable input-device preferences; discovery never opens an audio stream."""

from dataclasses import dataclass
import unicodedata


def _name(value):
    if not isinstance(value, str) or len(value) > 512 or any(ord(char) < 32 for char in value):
        raise ValueError("Invalid input-device name")
    return unicodedata.normalize("NFC", value.strip())


@dataclass(frozen=True)
class InputSelection:
    name: str = ""
    hostapi: str = ""

    def __post_init__(self):
        object.__setattr__(self, "name", _name(self.name))
        object.__setattr__(self, "hostapi", _name(self.hostapi))
        if bool(self.name) != bool(self.hostapi):
            raise ValueError("An input device needs its audio API")

    @classmethod
    def from_config(cls, config):
        recording = config.get("recording", {})
        return cls(recording.get("input_device", ""), recording.get("input_hostapi", ""))

    @property
    def key(self):
        return self.name.casefold(), self.hostapi.casefold()


@dataclass(frozen=True)
class InputDevice:
    index: int
    selection: InputSelection

    @property
    def label(self):
        return f"{self.selection.name} · {self.selection.hostapi}"


def list_inputs(*, backend=None):
    if backend is None:
        import sounddevice as backend
    devices, apis = backend.query_devices(), backend.query_hostapis()
    result = []
    for index, device in enumerate(devices):
        if device["max_input_channels"] > 0:
            selection = InputSelection(device["name"], apis[device["hostapi"]]["name"])
            if selection.name:
                result.append(InputDevice(index, selection))
    return tuple(result)


def resolve_input(selection, *, backend=None):
    if not selection.name:
        return None
    matches = [device.index for device in list_inputs(backend=backend)
        if device.selection.key == selection.key]
    if len(matches) != 1:
        raise RuntimeError("Selected microphone is unavailable or ambiguous")
    return matches[0]


def selected_input_stream(selection, **kwargs):
    import sounddevice as sd
    kwargs["device"] = resolve_input(selection, backend=sd)
    if selection.hostapi.casefold() == "windows wasapi":
        kwargs["extra_settings"] = sd.WasapiSettings(auto_convert=True)
    return sd.InputStream(**kwargs)
