"""Stable input-device preferences; discovery never opens an audio stream."""

from dataclasses import dataclass
import logging
import unicodedata

logger = logging.getLogger(__name__)


def routed_input(selection):
    """Known routed/system sources remain selectable, with an honest label."""
    name = selection.name.casefold()
    return any(value in name for value in ("vb-audio", "cable output", "voicemeeter",
        "stereo mix", "what u hear", "steam streaming", "loopback"))


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
        return " ".join(self.name.split()).casefold(), " ".join(self.hostapi.split()).casefold()


@dataclass(frozen=True)
class InputDevice:
    index: int
    selection: InputSelection
    is_default: bool = False

    @property
    def label(self):
        label = f"{self.selection.name} · {self.selection.hostapi}"
        return label + (" · Virtual / system audio" if routed_input(self.selection) else "")


def list_inputs(*, backend=None):
    if backend is None:
        import sounddevice as backend
    devices, apis = backend.query_devices(), backend.query_hostapis()
    try:
        default_index = backend.default.device[0]
    except (AttributeError, IndexError, TypeError):
        default_index = None
    result, skipped = [], 0
    for index, device in enumerate(devices):
        try:
            if device["max_input_channels"] <= 0:
                continue
            api = device["hostapi"]
            if type(api) is not int or not 0 <= api < len(apis):
                raise ValueError("Invalid audio API index")
            name, hostapi = device["name"], apis[api]["name"]
            if not isinstance(name, str) or not isinstance(hostapi, str):
                raise ValueError("Invalid input metadata")
            # Some Windows WDM-KS Bluetooth names contain CR/LF and tabs.
            # Normalize discovery labels, keeping strict config validation.
            selection = InputSelection(" ".join(name.split()), " ".join(hostapi.split()))
            if selection.name:
                result.append(InputDevice(index, selection, index == default_index))
        except (ValueError, KeyError, TypeError, IndexError):
            skipped += 1  # One malformed endpoint must not hide every working mic.
    if skipped:
        logger.warning("Skipped %d input endpoints with unusable metadata", skipped)
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
