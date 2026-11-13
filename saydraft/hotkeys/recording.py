"""Route named native transitions to recording gestures and History capture."""

from .chords import Binding, Chord, conflicts


def validate_hotkeys(hotkeys):
    """Validate saved or staged preferences with the native binding compiler."""
    keys = {name: hotkeys[name] for name in ("speech", "speech_alternative", "speech_mouse", "hands_free")
            if hotkeys.get(name, "").strip()}
    if not keys:
        return ["Enter at least one recording shortcut"]
    try:
        recording_bindings(keys, cancel_key=hotkeys.get("cancel", ""), save_key=hotkeys.get("save", ""),
                           paste_key=hotkeys.get("paste_last", ""), utility_keys={
                               name: hotkeys.get(name, '') for name in ('scratchpad', 'view_diff')})
    except ValueError as exc:
        return [str(exc)]
    return []


def recording_bindings(keys, *, cancel_key, save_key, paste_key="", suppress=True, utility_keys=None):
    """Compile and validate exactly the bindings installed by the app, without hooks."""
    def binding(name, key, **options):
        try:
            return Binding(name, Chord.parse(key), **options)
        except ValueError as exc:
            raise ValueError(f"{name}: {exc}") from exc

    bindings = [binding(name, key, suppress=suppress) for name, key in keys.items()]
    if cancel_key:
        bindings.append(binding("cancel", cancel_key, suppress=False, extra_modifiers=True))
    for name, key in (("save", save_key), ("paste_last", paste_key)):
        if key:
            command = binding(name, key)
            for previous in bindings:
                if (any(previous.chord.held(state) for state in command.chord.possibilities())
                        or any(command.chord.held(state) for state in previous.chord.possibilities())):
                    raise ValueError(f"Shortcut prefix conflict: {previous.name} and {name}")
            bindings.append(command)
    for name, key in (utility_keys or {}).items():
        if name not in ('scratchpad', 'view_diff'):
            raise ValueError('Unknown utility shortcut')
        if not key:
            continue
        command = binding(name, key)
        for previous in bindings:
            # Ctrl+Win+D may supersede the Ctrl+Win recording prefix. Never
            # allow a utility prefix to shadow recording or another action.
            shadows = any(command.chord.held(state) for state in previous.chord.possibilities())
            extends = any(previous.chord.held(state) for state in command.chord.possibilities())
            recording = previous.name in keys and previous.name != 'hands_free'
            if shadows or extends and not recording:
                raise ValueError(f'Shortcut prefix conflict: {previous.name} and {name}')
        bindings.append(command)
    overlap = conflicts(bindings)
    if overlap:
        raise ValueError("Shortcut conflict: " + "; ".join(f"{a} and {b}" for a, b in overlap))
    return bindings


class RecordingHooks:
    def __init__(self, keys, *, cancel_key, save_key, suppress, press, release, cancel, save, failure, factory=None,
                 hands_free_key=None, toggle=None, paste_key=None, paste=None, utility_keys=None, utility=None,
                 cancel_prefix=None):
        if factory is None:
            from .llhook import LowLevelHooks
            factory = LowLevelHooks
        self.keys = {f"record{index}": key for index, key in enumerate(keys)}
        if hands_free_key:
            self.keys["hands_free"] = hands_free_key
        bindings = recording_bindings(self.keys, cancel_key=cancel_key,
            save_key=save_key if save is not None else "", paste_key=paste_key if paste is not None else "",
            suppress=suppress, utility_keys=utility_keys)
        self.press, self.release, self.cancel, self.save = press, release, cancel, save
        self.toggle = toggle
        self.paste = paste
        self.utility_keys, self.utility = utility_keys or {}, utility
        self.cancel_prefix = cancel_prefix or cancel
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
            elif transition.superseded_by in self.utility_keys:
                self.cancel_prefix(when)
        elif transition.name in self.utility_keys:
            if transition.phase == 'release' and transition.reason == 'physical' and self.utility is not None:
                self.utility(transition.name)
        elif transition.name == "paste_last":
            if transition.phase == "release" and transition.reason == "physical" and self.paste is not None:
                self.paste()
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
