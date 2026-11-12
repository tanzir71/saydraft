"""Route named native transitions to recording gestures and History capture."""

from .chords import Binding, Chord


class RecordingHooks:
    def __init__(self, keys, *, cancel_key, save_key, suppress, press, release, cancel, save, failure, factory=None):
        if factory is None:
            from .llhook import LowLevelHooks
            factory = LowLevelHooks
        self.keys = {f"record{index}": key for index, key in enumerate(keys)}
        bindings = [Binding(name, Chord.parse(key), suppress=suppress) for name, key in self.keys.items()]
        if cancel_key:
            bindings.append(Binding("cancel", Chord.parse(cancel_key), suppress=False, extra_modifiers=True))
        if save_key and save is not None:
            saved = Binding("save", Chord.parse(save_key))
            for record in bindings:
                if record.name in self.keys and (any(record.chord.held(keys) for keys in saved.chord.possibilities())
                        or any(saved.chord.held(keys) for keys in record.chord.possibilities())):
                    raise ValueError("History and recording shortcuts share a prefix")
            bindings.append(saved)
        self.press, self.release, self.cancel, self.save = press, release, cancel, save
        self.owner = factory(bindings, on_action=self._action, on_failure=failure)

    def _action(self, transition, when):
        if transition.name in self.keys:
            key = self.keys[transition.name]
            if transition.phase == "press":
                self.press(key, when, retarget=True)
            elif transition.reason != "superseded":
                self.release(key, when)
        elif transition.phase == "press":
            if transition.name == "cancel":
                self.cancel(when)
            elif transition.name == "save" and self.save is not None:
                self.save()

    @property
    def completion_thread(self):
        return self.owner.completion_thread

    @property
    def alive(self):
        return self.owner.status["state"] == "running"

    def start(self):
        self.owner.start()

    def close(self):
        return self.owner.close()
