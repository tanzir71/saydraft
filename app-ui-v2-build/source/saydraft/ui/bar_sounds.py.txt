"""Original Bar cues, with generation/phase guards for asynchronous loading."""

from __future__ import annotations

from contextlib import ExitStack
import hashlib
from importlib.resources import as_file, files
import json
import logging
import time

from saydraft.core.bar_status import BarPhase, BarUpdate
from . import sound_assets

logger = logging.getLogger(__name__)


class SilentSounds:
    def request(self, cue, valid):
        return False

    def cancel_pending(self):
        pass

    def close(self):
        pass


class QtSoundBank:
    """Keep decoded effects ready; never play an obsolete pending cue."""

    def __init__(self, parent, *, effect_factory=None, clock=time.monotonic):
        from PySide6 import QtCore
        if effect_factory is None:
            from PySide6.QtMultimedia import QSoundEffect
            effect_factory = QSoundEffect
        self._qt = QtCore
        self.clock = clock
        self._ready = effect_factory.Status.Ready
        self._error = effect_factory.Status.Error
        self._effects, self._callbacks, self._pending = {}, {}, {}
        self._resources = ExitStack()
        self.closed = False
        try:
            root = files(sound_assets)
            manifest = json.loads(root.joinpath("manifest.json").read_text("utf-8"))
            for name in ("start", "end", "command"):
                entry = manifest["cues"][name]
                if entry["file"] != f"{name}.wav":
                    raise ValueError("Invalid sound resource name")
                resource = root.joinpath(entry["file"])
                if hashlib.sha256(resource.read_bytes()).hexdigest() != entry["sha256"]:
                    raise ValueError("Sound resource checksum mismatch")
                path = self._resources.enter_context(as_file(resource))
                effect = effect_factory(parent)
                self._effects[name] = effect
                effect.setLoopCount(1)
                effect.setVolume(1.)
                def callback(name=name):
                    self._flush(name)
                self._callbacks[name] = callback
                effect.statusChanged.connect(callback)
                effect.setSource(QtCore.QUrl.fromLocalFile(str(path)))
        except Exception:
            self.close()
            raise

    def request(self, cue, valid):
        if self.closed or cue not in self._effects:
            return False
        self._pending[cue] = valid, self.clock() + .120
        self._flush(cue)
        return True

    def _flush(self, cue):
        if self.closed or cue not in self._pending:
            return
        effect = self._effects[cue]
        if effect.status() == self._error:
            self._pending.pop(cue, None)
            logger.debug("Bar sound unavailable")
        elif effect.status() == self._ready:
            valid, deadline = self._pending.pop(cue)
            try:
                if self.clock() <= deadline and valid():
                    effect.play()
            except Exception:
                logger.debug("Bar sound request expired or unavailable")

    def cancel_pending(self):
        self._pending.clear()

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.cancel_pending()
        for name, effect in self._effects.items():
            try:
                callback = self._callbacks.get(name)
                if callback is not None:
                    effect.statusChanged.disconnect(callback)
            except (RuntimeError, TypeError):
                pass
            try:
                effect.stop()
                effect.setSource(self._qt.QUrl())
                effect.deleteLater()
            except (RuntimeError, TypeError):
                logger.debug("Bar sound effect already retired")
        self._effects.clear()
        self._callbacks.clear()
        self._resources.close()


def sound_bank(application):
    # Offscreen tests and galleries must never initialize an output device.
    if application.platformName() != "windows":
        return SilentSounds()
    try:
        return QtSoundBank(application)
    except Exception:
        logger.warning("Bar sounds unavailable; dictation remains available")
        return SilentSounds()


class BarSoundPresenter:
    def __init__(self, bank, *, current, state, config):
        self.bank, self.current, self.state, self.config = bank, current, state, config
        self.closed = False
        self.generation = -1
        self.seen = set()

    def _enabled(self, cue):
        app = (self.config() or {}).get("app", {})
        return bool(app.get("end_sound", False) if cue == "end" else app.get("start_sound", True))

    def _valid(self, generation, cue):
        states = ("idle", "hover", "hidden") if cue == "end" else ("recording", "command")
        return (not self.closed and self.current(generation) and self.state() in states and self._enabled(cue))

    def handle(self, update):
        if (self.closed or not isinstance(update, BarUpdate) or not self.current(update.generation)
                or update.generation < self.generation):
            return
        if update.generation != self.generation:
            self.generation = update.generation
            self.seen.clear()
        cue = ("command" if update.reason == "command" else "start") if update.phase == BarPhase.LISTENING else "end" if update.phase == BarPhase.INSERTED else None
        key = update.phase, cue
        if key in self.seen:
            return
        self.seen.add(key)
        self.bank.cancel_pending()
        if cue is not None and self._enabled(cue):
            self.bank.request(cue, lambda: self._valid(update.generation, cue))

    def close(self):
        self.closed = True
        self.bank.close()
