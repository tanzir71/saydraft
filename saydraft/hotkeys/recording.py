"""Route named native transitions to recording gestures and History capture."""

from .chords import Binding, Chord, conflicts


def recording_bindings(keys, *, cancel_key, save_key, suppress=True):
    """Compile and validate exactly the bindings installed by the app, without hooks."""
    def binding(name, key, **options):
        try:
            return Binding(name, Chord.parse(key), **options)
        except ValueError as exc:
            raise ValueError(f"{name}: {exc}") from exc

    bindings = [binding(name, key, suppress=suppress) for name, key in keys.items()]
    if cancel_key:
        bindings.append(binding("cancel", cancel_key, suppress=False, extra_modifiers=True))
    if save_key:
        saved = binding("save", save_key)
        for record in bindings:
            if record.name in keys and (any(record.chord.held(state) for state in saved.chord.possibilities())
                    or any(saved.chord.held(state) for state in record.chord.possibilities())):
                raise ValueError(f"History and recording shortcuts share a prefix ({record.name}, save)")
        bindings.append(saved)
    overlap = conflicts(bindings)
    if overlap:
        raise ValueError("Shortcut conflict: " + "; ".join(f"{a} and {b}" for a, b in overlap))
    return bindings


class RecordingHooks:
    def __init__(self, keys, *, cancel_key, save_key, suppress, press, release, cancel, save, failure, factory=None,
                 hands_free_key=None, toggle=None):
        if factory is None:
            from .llhook import LowLevelHooks
            factory = LowLevelHooks
        self.keys = {f"record{index}": key for index, key in enumerate(keys)}
        if hands_free_key:
            self.keys["hands_free"] = hands_free_key
        bindings = recording_bindings(self.keys, cancel_key=cancel_key,
            save_key=save_key if save is not None else "", suppress=suppress)
        self.press, self.release, self.cancel, self.save = press, release, cancel, save
        self.toggle = toggle
        self.owner = factory(bindings, on_action=self._action, on_failure=failure)

    def _action(self, transition, when):
        if transition.name == "hands_free":
            if transition.phase == "press" and self.toggle is not None:
                self.toggle(when)
        elif transition.name in self.keys:
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

    def defer(self, callback):
        return self.owner.post_action(callback)

    @property
    def alive(self):
        return self.owner.status["state"] == "running"

    def start(self):
        self.owner.start()

    def close(self):
        return self.owner.close()
