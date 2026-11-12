import hashlib
from importlib.resources import files
import io
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
from types import SimpleNamespace
import wave

import pytest

from saydraft.config import default_config
from saydraft.core.bar_status import BarPhase as Phase, BarUpdate
from saydraft.ui.bar_sounds import BarSoundPresenter, QtSoundBank, SilentSounds, sound_bank
from tests.test_bar_placement import Signal
from tests.test_pill_ui import qt_modules
from tools.generate_bar_sounds import generate, loudness_400ms


class FakeBank:
    def __init__(self):
        self.requests, self.pending, self.played = [], {}, []
        self.closed = False

    def request(self, cue, valid):
        self.requests.append(cue)
        self.pending[cue] = valid

    def cancel_pending(self):
        self.pending.clear()

    def ready(self, cue):
        valid = self.pending.pop(cue, None)
        if valid is not None and valid():
            self.played.append(cue)

    def close(self):
        self.closed = True
        self.pending.clear()


class Effect:
    Status = SimpleNamespace(Loading=1, Ready=2, Error=3)
    instances = []

    def __init__(self, parent):
        self.instances.append(self)
        self.parent = parent
        self.statusChanged = Signal()
        self.value = self.Status.Loading
        self.plays = self.stops = self.deleted = 0

    def status(self):
        return self.value

    def setLoopCount(self, count):
        self.loops = count

    def setVolume(self, volume):
        self.volume = volume

    def setSource(self, source):
        self.source = source

    def play(self):
        self.plays += 1  # Stub only: no QSoundEffect or output device exists.

    def stop(self):
        self.stops += 1

    def deleteLater(self):
        self.deleted += 1

    def ready(self):
        self.value = self.Status.Ready
        self.statusChanged.emit()


def presenter():
    bank = FakeBank()
    generation, state, config = [1], ["recording"], default_config()
    sounds = BarSoundPresenter(bank, current=lambda value: value == generation[0],
        state=lambda: state[0], config=lambda: config)
    return sounds, bank, generation, state, config


def test_original_assets_are_short_distinct_licensed_and_reproducible():
    manifest = generate(check=True)
    root = files("saydraft.ui.sound_assets")
    assert manifest["license"] == "MIT" and manifest["sample_rate"] == 48000
    assert root.joinpath("LICENSE").read_text("utf-8").replace("\r\n", "\n") == (Path(__file__).parents[1] / "LICENSE").read_text("utf-8")
    hashes = set()
    for name, entry in manifest["cues"].items():
        raw = root.joinpath(entry["file"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == entry["sha256"]
        hashes.add(entry["sha256"])
        with wave.open(io.BytesIO(raw), "rb") as source:
            assert source.getnchannels() == 1 and source.getsampwidth() == 2
            assert source.getframerate() == 48000 and source.getnframes() <= 5760
            frames = source.readframes(source.getnframes())
        samples = [value / 32768 for (value,) in struct.iter_unpack("<h", frames)]
        assert abs(samples[0]) == 0 and abs(samples[-1]) <= 1 / 32768
        assert 20 * math.log10(max(abs(value) for value in samples)) < -1
        assert loudness_400ms(samples) == pytest.approx(-24 if name == "end" else -18, abs=.02)
    assert len(hashes) == 3


def test_start_defaults_on_end_defaults_off_and_duplicate_loading_cue_is_preserved():
    sounds, bank, _, state, _ = presenter()
    state[0] = "preparing"
    sounds.handle(BarUpdate(1, Phase.PREPARING))
    assert not bank.requests
    state[0] = "recording"
    sounds.handle(BarUpdate(1, Phase.LISTENING))
    sounds.handle(BarUpdate(1, Phase.LISTENING))
    assert bank.requests == ["start"] and "start" in bank.pending
    bank.ready("start")
    state[0] = "idle"
    sounds.handle(BarUpdate(1, Phase.INSERTED, saved=True))
    assert bank.played == ["start"] and bank.requests == ["start"]


@pytest.mark.parametrize("phase", [Phase.PROCESSING, Phase.IDLE, Phase.NOT_INSERTED, Phase.ERROR])
def test_completion_refusal_error_and_cancel_do_not_play_success_or_late_start(phase):
    sounds, bank, _, state, config = presenter()
    config["app"]["end_sound"] = True
    sounds.handle(BarUpdate(1, Phase.LISTENING))
    state[0] = "warning" if phase == Phase.NOT_INSERTED else "processing"
    sounds.handle(BarUpdate(1, phase))
    bank.ready("start")
    assert not bank.played and bank.requests == ["start"]


@pytest.mark.parametrize("idle_state", ["idle", "hover", "hidden"])
def test_optional_end_requires_actual_insertion_and_respects_new_generation(idle_state):
    sounds, bank, generation, state, config = presenter()
    config["app"]["end_sound"] = True
    state[0] = idle_state
    sounds.handle(BarUpdate(1, Phase.INSERTED, saved=True))
    assert bank.requests == ["end"]
    generation[0] = 2
    bank.ready("end")
    assert not bank.played
    state[0] = idle_state
    sounds.handle(BarUpdate(2, Phase.INSERTED, saved=True))
    bank.ready("end")
    assert bank.played == ["end"]


def test_muting_applies_to_pending_loads_and_does_not_play_retroactively():
    sounds, bank, generation, _, config = presenter()
    sounds.handle(BarUpdate(1, Phase.LISTENING))
    config["app"]["start_sound"] = False
    bank.ready("start")
    assert not bank.played
    config["app"]["start_sound"] = True
    sounds.handle(BarUpdate(1, Phase.LISTENING))
    assert bank.requests == ["start"]
    generation[0] = 2
    sounds.handle(BarUpdate(2, Phase.LISTENING))
    bank.ready("start")
    assert bank.played == ["start"]


def test_command_cue_is_distinct_and_closing_suppresses_pending_audio():
    sounds, bank, _, state, _ = presenter()
    state[0] = "command"
    sounds.handle(BarUpdate(1, Phase.LISTENING, reason="command"))
    assert bank.requests == ["command"]
    sounds.close()
    bank.ready("command")
    assert bank.closed and not bank.played


@pytest.mark.parametrize("expired", [False, True])
def test_qt_adapter_loads_local_assets_once_and_discards_cues_over_120_ms(expired):
    qt_modules()
    Effect.instances = []
    clock = [0.]
    bank = QtSoundBank(None, effect_factory=Effect, clock=lambda: clock[0])
    assert len(Effect.instances) == 3
    start = bank._effects["start"]
    assert start.source.isLocalFile() and Path(start.source.toLocalFile()).name == "start.wav"
    assert start.loops == 1 and start.volume == 1
    bank.request("start", lambda: True)
    assert start.plays == 0
    clock[0] = .121 if expired else .01
    start.ready()
    assert start.plays == (0 if expired else 1)
    bank.close()
    bank.close()
    assert all(effect.stops == 1 and effect.deleted == 1 for effect in Effect.instances)
    assert all(not effect.statusChanged.callbacks for effect in Effect.instances)


def test_load_failure_and_invalidated_generation_never_play():
    qt_modules()
    bank = QtSoundBank(None, effect_factory=Effect)
    start, command = bank._effects["start"], bank._effects["command"]
    bank.request("start", lambda: False)
    start.ready()
    bank.request("command", lambda: True)
    command.value = command.Status.Error
    command.statusChanged.emit()
    assert start.plays == command.plays == 0 and not bank._pending
    bank.close()


def test_offscreen_sound_bank_never_constructs_a_multimedia_backend(monkeypatch):
    from saydraft.ui import bar_sounds

    def forbidden(*args, **kwargs):
        pytest.fail("Audio backend initialized during offscreen QA")

    monkeypatch.setattr(bar_sounds, "QtSoundBank", forbidden)
    assert isinstance(sound_bank(SimpleNamespace(platformName=lambda: "offscreen")), SilentSounds)


def test_backend_failure_falls_back_without_blocking_dictation(monkeypatch):
    from saydraft.ui import bar_sounds

    def fail(*args):
        raise OSError("fixture output device unavailable")

    monkeypatch.setattr(bar_sounds, "QtSoundBank", fail)
    bank = sound_bank(SimpleNamespace(platformName=lambda: "windows"))
    assert isinstance(bank, SilentSounds)
    assert bank.request("start", lambda: True) is False


def test_resource_failure_retires_already_prepared_effects(tmp_path, monkeypatch):
    from saydraft.ui import bar_sounds

    qt_modules()
    root = files("saydraft.ui.sound_assets")
    manifest = json.loads(root.joinpath("manifest.json").read_text("utf-8"))
    for name in ("start.wav", "end.wav", "command.wav"):
        (tmp_path / name).write_bytes(root.joinpath(name).read_bytes())
    manifest["cues"]["end"]["sha256"] = "0" * 64
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(bar_sounds, "files", lambda package: tmp_path)
    Effect.instances = []
    with pytest.raises(ValueError, match="checksum"):
        QtSoundBank(None, effect_factory=Effect)
    assert len(Effect.instances) == 1
    assert Effect.instances[0].stops == Effect.instances[0].deleted == 1
    assert not Effect.instances[0].statusChanged.callbacks


def test_packager_collects_the_three_wavs_manifest_and_license():
    script = "from PyInstaller.utils.hooks import collect_data_files; from pathlib import Path; import json; print(json.dumps([Path(source).name for source, _ in collect_data_files('saydraft.ui.sound_assets')]))"
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True)
    names = set(json.loads(result.stdout))
    assert {"start.wav", "end.wav", "command.wav", "manifest.json", "LICENSE"} <= names


def test_app_command_event_selects_the_command_bar_and_cue_without_real_playback():
    from saydraft.app import SaydraftApp
    from saydraft.ui.pill import PillState, SaydraftPill

    qt = qt_modules()
    config = default_config()
    app = SaydraftApp()
    generation = [1]
    app.controller = SimpleNamespace(is_current_bar=lambda value: value == generation[0], is_hands_free=lambda: False)
    app.pill = SaydraftPill(screen_geometry_provider=lambda: qt.QtCore.QRect(0, 0, 1000, 800))
    bank = FakeBank()
    app.bar_sounds = BarSoundPresenter(bank, current=app.controller.is_current_bar,
        state=lambda: app.pill.state, config=lambda: config)
    try:
        app._apply_bar_update(BarUpdate(1, Phase.LISTENING, reason="command"))
        assert app.pill.state == PillState.COMMAND and bank.requests == ["command"]
        bank.ready("command")
        assert bank.played == ["command"]
        generation[0] = 2
        app._apply_bar_update(BarUpdate(1, Phase.LISTENING))
        assert bank.requests == ["command"]
    finally:
        app.bar_sounds.close()
        app.pill.hide()
