"""A temporary chord matcher that permanently revokes on loss of its owned target."""

from .chords import ChordMatcher, Decision, Transition
from .keys import MODIFIERS

TARGET_LOST = 'practice_target_lost'


class FocusedMatcher:
    def __init__(self, bindings, *, valid):
        self.matcher = ChordMatcher(bindings)
        self.valid = valid
        self.revoked = False
        self.blocked = set()

    def seed(self, keys):
        self.matcher.seed(keys)

    def feed(self, key, down, *, ignore=False):
        if ignore or key is None:
            return Decision()
        suppressed = key in self.blocked
        if not down:
            self.blocked.discard(key)
        try:
            allowed = not self.revoked and self.valid()
        except Exception:
            allowed = False
        if not allowed:
            first = not self.revoked
            reset = self.matcher.reset() if first else Decision()
            self.revoked = True
            return Decision((Transition(TARGET_LOST, 'revoked'),) if first else (), suppress=suppressed,
                menu_mask=reset.menu_mask or not down and suppressed and key in MODIFIERS['win'] | MODIFIERS['alt'])
        decision = self.matcher.feed(key, down)
        if down and decision.suppress:
            self.blocked.add(key)
        return decision

    def reset(self):
        decision = self.matcher.reset()
        mask = decision.menu_mask or bool(self.blocked & (MODIFIERS['win'] | MODIFIERS['alt']))
        self.blocked.clear()
        self.revoked = True
        return Decision(menu_mask=mask)
