"""Released Command gesture -> explicit guarded selection copy -> original lease."""

from dataclasses import dataclass
import time


@dataclass(frozen=True)
class CommandCopyResult:
    captured: object = None
    reason: str = "copy_unavailable"
    restore_pending: bool = False


def capture_command_copy(captured, *, context, inserter, current, clock=time.monotonic, sleep=time.sleep):
    """Worker only. Never release physical keys or hold the session mutex here."""
    clipboard = getattr(inserter, 'clipboard', None)
    capture = getattr(clipboard, 'capture_selection', None)
    delivery = getattr(inserter, 'delivery_guard', None)
    keyboard = getattr(inserter, 'keyboard', None)
    if (captured.selection.status != 'copy_pending' or captured.selection.origin != 'clipboard'
            or not callable(capture) or not callable(delivery) or not callable(getattr(keyboard, 'send', None))):
        return CommandCopyResult()

    def guard():
        if not current():
            return 'cancelled'
        reason = context.verify_selection(captured, for_write=False)
        if reason or not current():
            return reason or 'cancelled'
        reason = delivery(captured.target.focus)
        return reason if current() else 'cancelled'

    try:
        deadline = clock() + .75
        while True:
            reason = guard()
            if reason != 'modifier_held':
                break
            if clock() >= deadline:
                return CommandCopyResult(reason='modifier_held')
            sleep(min(.01, max(0, deadline - clock())))
        if reason:
            return CommandCopyResult(reason=reason)
        result = capture(process_id=captured.target.process_id, guard=guard,
            send_copy=lambda: keyboard.send('ctrl+c'), current=current, clock=clock, sleep=sleep)
        if result.reason != 'ok' or not current():
            return CommandCopyResult(reason=result.reason if current() else 'cancelled',
                                     restore_pending=result.restore_status == 'pending')
        sealed = context.seal_copy(captured, result.text)
        if sealed.selection.status != 'ready' or not current():
            return CommandCopyResult(reason=sealed.selection.status if current() else 'cancelled')
        return CommandCopyResult(sealed, 'ok')
    except Exception:
        return CommandCopyResult(reason='copy_unavailable')
