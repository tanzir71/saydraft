"""Bounded pure chord matching and balanced suppression for low-level hooks."""

from dataclasses import dataclass
from itertools import product

from .keys import MODIFIERS, PHYSICAL_MODIFIERS, normalize_key


def _covers(required, physical):
    return required == physical or physical in MODIFIERS.get(required, ())


@dataclass(frozen=True)
class Chord:
    keys: frozenset[str]

    def __post_init__(self):
        if (not isinstance(self.keys, frozenset) or not 0 < len(self.keys) <= 8
                or any(not isinstance(key, str) or normalize_key(key) != key for key in self.keys)
                or any(name in self.keys and sides & self.keys for name, sides in MODIFIERS.items())
                or len(self.keys - PHYSICAL_MODIFIERS - MODIFIERS.keys()) > 1):
            raise ValueError("Invalid canonical hotkey chord")

    @classmethod
    def parse(cls, value):
        if not isinstance(value, str) or not value.strip() or len(value) > 128:
            raise ValueError("Enter a nonempty hotkey of at most 128 characters")
        parts = value.split("+")
        keys = frozenset(normalize_key(part) for part in parts)
        if len(keys) != len(parts) or len(keys) > 8:
            raise ValueError("Hotkeys require distinct keys, with at most eight keys")
        return cls(keys)

    def held(self, down):
        return all(required in down or any(side in down for side in MODIFIERS.get(required, ()))
                   for required in self.keys)

    def covers(self, key):
        return any(_covers(required, key) for required in self.keys)

    def possibilities(self):
        return (frozenset(keys) for keys in product(*(MODIFIERS.get(key, (key,)) for key in sorted(self.keys))))


@dataclass(frozen=True)
class Binding:
    name: str
    chord: Chord
    suppress: bool = True
    priority: int = 0
    extra_modifiers: bool = False

    def __post_init__(self):
        if (not isinstance(self.name, str) or not 0 < len(self.name) <= 64 or not isinstance(self.chord, Chord)
                or type(self.suppress) is not bool or type(self.extra_modifiers) is not bool
                or type(self.priority) is not int or not -64 <= self.priority <= 64):
            raise ValueError("Invalid hotkey binding")

    def matches(self, down):
        return self.chord.held(down) and all(self.chord.covers(key)
            or self.extra_modifiers and key in PHYSICAL_MODIFIERS for key in down)

    @property
    def rank(self):
        return self.priority, len(self.chord.keys), len(self.chord.keys & PHYSICAL_MODIFIERS)


def conflicts(bindings):
    result = []
    for index, a in enumerate(bindings):
        for b in bindings[index + 1:]:
            if any(a.matches(keys) and b.matches(keys) for keys in
                   (*a.chord.possibilities(), *b.chord.possibilities())):
                result.append((a.name, b.name))
    return result


@dataclass(frozen=True)
class Transition:
    name: str
    phase: str
    reason: str = "physical"


@dataclass(frozen=True)
class Decision:
    transitions: tuple[Transition, ...] = ()
    suppress: bool = False
    menu_mask: bool = False


class ChordMatcher:
    def __init__(self, bindings):
        self.bindings = tuple(bindings)
        if (len(self.bindings) > 64 or len({item.name for item in self.bindings}) != len(self.bindings)
                or conflicts(self.bindings)):
            raise ValueError("Hotkey bindings conflict or exceed 64 actions")
        self._down, self._suppressed, self._mask = set(), set(), set()
        self._active = None

    def seed(self, keys):
        """Startup state only; already held keys neither fire nor become suppressed."""
        keys = frozenset(keys)
        if self._down or self._active is not None:
            raise RuntimeError("Seed only an unused chord matcher")
        if len(keys) > 254 or any(key in MODIFIERS or normalize_key(key) != key for key in keys):
            raise ValueError("Expected bounded canonical physical key state")
        self._down.update(keys)

    def feed(self, key, down, *, ignore=False):
        # Native decoding supplies physical names. No key text/history is retained.
        if ignore or key is None:
            return Decision()
        if type(down) is not bool or not isinstance(key, str) or key in MODIFIERS or normalize_key(key) != key:
            raise ValueError("Expected a canonical physical key event")
        if down and key in self._down:
            return Decision(suppress=key in self._suppressed)
        if not down and key not in self._down:
            return Decision()
        if down:
            self._down.add(key)
        else:
            self._down.remove(key)
        mask = not down and key in self._mask
        if not down:
            self._mask.discard(key)
        suppressed = not down and key in self._suppressed
        if not down:
            self._suppressed.discard(key)
        transitions = []
        if self._active is not None and not self._active.chord.held(self._down):
            transitions.append(Transition(self._active.name, "release"))
            self._active = None
        if down:
            best = max((item for item in self.bindings if item.matches(self._down)), key=lambda item: item.rank,
                       default=None)
            if best is not None and best != self._active and (self._active is None
                    or not self._active.matches(self._down) or best.rank > self._active.rank):
                if self._active is not None:
                    transitions.append(Transition(self._active.name, "release", "superseded"))
                self._active = best
                transitions.append(Transition(best.name, "press"))
            if self._active is not None and self._active.chord.covers(key):
                if self._active.suppress:
                    self._suppressed.add(key)
                    suppressed = True
                if self._active.suppress:
                    self._mask.update(physical for physical in self._down
                        if physical in MODIFIERS["win"] | MODIFIERS["alt"] and self._active.chord.covers(physical))
        return Decision(tuple(transitions), suppressed, mask)

    def reset(self):
        transitions = (Transition(self._active.name, "release", "reset"),) if self._active is not None else ()
        decision = Decision(transitions, menu_mask=bool(self._mask))
        self._active = None
        self._down.clear()
        self._suppressed.clear()
        self._mask.clear()
        return decision
