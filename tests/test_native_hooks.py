"""Native transport contracts with a deterministic message-pump API; no OS input."""

import ctypes as c
import queue
import threading
from types import SimpleNamespace

import pytest

from saydraft.hotkeys._win32_hooks import KeyboardPacket, MousePacket, Win32Hooks, mask_input
from saydraft.hotkeys.chords import Binding, Chord
from saydraft.hotkeys.llhook import LowLevelHooks
from saydraft.input_origin import SAYDRAFT_INPUT_TAG


class API:
    def __init__(self, failure=None):
        self.tasks, self.trace, self.failure = queue.Queue(), [], failure
        self.closed = False

    def install(self, keyboard, mouse):
        self.keyboard, self.mouse, self.thread_id = keyboard, mouse, threading.get_ident()
        self.trace.append("installed_keyboard")
        if self.failure == "install":
            raise OSError("private error")
        self.trace.append("installed_mouse")

    def next_message(self):
        task = self.tasks.get()
        if task is None:
            return False
        task()
        return True

    def pressed_keys(self):
        return []

    def wake(self):
        self.tasks.put(None)

    def forward(self, *args):
        self.trace.append("forward")
        if self.failure == "forward":
            raise OSError("private error")
        return 17

    def mask(self):
        self.trace.append("mask")
        if self.failure == "mask":
            raise OSError("private error")

    def close(self):
        self.closed = True
        self.trace.append("closed")
        if self.failure == "close":
            raise OSError("private error")

    def emit(self, kind, message, packet, code=0):
        result, done = [], threading.Event()
        def task():
            result.append(getattr(self, kind)(code, message, c.addressof(packet) if packet else 0))
            done.set()
        self.tasks.put(task)
        assert done.wait(3)
        return result[0]


def rig(*, action=None, failure=None, capacity=64):
    api, actions, failures = API(failure), [], []
    hooks = LowLevelHooks([Binding("ptt", Chord.parse("ctrl+win")), Binding("probe", Chord.parse("vkE8")),
        Binding("mouse", Chord.parse("xbutton1"))], api_factory=lambda: api, clock=lambda: 7.25, capacity=capacity,
        on_action=action or (lambda value, when: actions.append((value, when, threading.get_ident()))),
        on_failure=lambda reason: failures.append((reason, threading.get_ident(), api.closed)))
    return hooks, api, actions, failures


def test_keyboard_mouse_forwarding_mask_order_and_callback_thread():
    hooks, api, actions, _ = rig()
    assert hooks.start()
    try:
        assert api.emit("keyboard", 0x100, KeyboardPacket(0x5B)) == 17
        assert api.emit("keyboard", 0x100, KeyboardPacket(0xA2)) == 1
        assert api.emit("keyboard", 0x101, KeyboardPacket(0xA2)) == 1
        before = len(api.trace)
        assert api.emit("keyboard", 0x101, KeyboardPacket(0x5B)) == 17
        assert api.trace[before:] == ["mask", "forward"]
        mouse = MousePacket(mouseData=1 << 16)
        assert api.emit("mouse", 0x20B, mouse) == 1
        assert api.emit("mouse", 0x20C, mouse) == 1
        assert api.emit("mouse", 0x200, None) == 17
        assert api.emit("keyboard", 0x100, None, code=-1) == 17
        # Complete a dispatcher barrier before close drops pending actions.
        done = threading.Event()
        original = hooks._on_action
        hooks._on_action = lambda *args: (original(*args), done.set())
        api.emit("keyboard", 0x100, KeyboardPacket(0xE8))
        assert done.wait(3)
        assert any(row[0].name == "mouse" for row in actions)
        assert all(row[1] == 7.25 and row[2] != api.thread_id for row in actions)
    finally:
        assert hooks.close() and api.closed
    assert hooks.status["state"] == "closed"


def test_own_tag_is_ignored_without_disabling_external_macro_or_accessibility_input():
    done = threading.Event()
    actions = []
    hooks, api, _, _ = rig(action=lambda transition, when: (actions.append(transition.phase), done.set()))
    hooks.start()
    try:
        for message in (0x100, 0x101):
            assert api.emit("keyboard", message, KeyboardPacket(0xE8, flags=0x10, dwExtraInfo=SAYDRAFT_INPUT_TAG)) == 17
        assert not actions
        assert api.emit("keyboard", 0x100, KeyboardPacket(0xE8, flags=0x10)) == 1
        assert done.wait(3) and actions == ["press"]
    finally:
        hooks.close()


@pytest.mark.parametrize("deferred", [False, True])
def test_slow_callback_does_not_block_hook_and_full_queue_stops_without_replaying_actions(deferred):
    entered, release = threading.Event(), threading.Event()
    calls = []
    def block(transition, when):
        calls.append(transition.phase)
        entered.set()
        assert release.wait(3)
    hooks, api, _, failures = rig(action=block, capacity=2)
    hooks.start()
    try:
        assert api.emit("keyboard", 0x100, KeyboardPacket(0xE8)) == 1 and entered.wait(3)
        if deferred:
            assert hooks.post_action(lambda: pytest.fail("Abandoned deferred work was replayed"))
            assert hooks.post_action(lambda: pytest.fail("Abandoned deferred work was replayed"))
            assert not hooks.post_action(lambda: pytest.fail("Full queue accepted work"))
        else:
            assert api.emit("keyboard", 0x101, KeyboardPacket(0xE8)) == 1
            assert api.emit("keyboard", 0x100, KeyboardPacket(0xE8)) == 1
            assert api.emit("keyboard", 0x101, KeyboardPacket(0xE8)) == 17
        assert hooks.status["reason"] == "action_queue_full"
        assert not hooks.close(timeout=0) and hooks.status["worker_alive"]
    finally:
        release.set()
        assert hooks.close()
    assert calls == ["press"] and len(failures) == 1 and failures[0][0] == "action_queue_full"
    assert failures[0][1] != api.thread_id and failures[0][2]


@pytest.mark.parametrize("failure,reason", [("install", "native_hook_failed"), ("mask", "mask_unavailable"),
    ("close", "unhook_failed"), ("forward", "forward_failed")])
def test_startup_callback_and_removal_failures_are_metadata_only_and_observed_after_cleanup(failure, reason):
    hooks, api, _, failures = rig(failure=failure)
    if failure == "install":
        with pytest.raises(OSError):
            hooks.start()
    else:
        hooks.start()
        if failure == "mask":
            api.emit("keyboard", 0x100, KeyboardPacket(0x5B))
            api.emit("keyboard", 0x100, KeyboardPacket(0xA2))
            api.emit("keyboard", 0x101, KeyboardPacket(0x5B))
        if failure == "forward":
            assert api.emit("keyboard", 0x100, None, code=-1) == 0
    assert hooks.close() and api.closed
    assert failures == [(reason, hooks._worker.ident, True)]
    assert hooks.status["reason"] == reason and "private" not in repr(hooks.status)


def test_action_exception_cannot_escape_worker_or_leave_hooks_installed():
    def fail(*args):
        raise ValueError("private text")
    hooks, api, _, failures = rig(action=fail)
    hooks.start()
    api.emit("keyboard", 0x100, KeyboardPacket(0xE8))
    assert hooks._pump_done.wait(3) and hooks.close()
    assert failures == [("action_failed", hooks._worker.ident, True)]


def test_thread_adoption_failure_retires_both_threads_and_native_hooks():
    api = API()
    class Adopted(threading.Thread):
        def start(self):
            super().start()
            if self.name.endswith("native-hooks"):
                raise RuntimeError("after adoption")
    hooks = LowLevelHooks([], on_action=lambda *args: None, api_factory=lambda: api, thread_factory=Adopted)
    with pytest.raises(RuntimeError):
        hooks.start()
    assert hooks.close() and api.closed


@pytest.mark.parametrize("count", [0, 1])
def test_partial_mask_delivery_retries_only_a_tagged_release(count):
    calls = []
    def send(size, values, structure_size):
        calls.append([(value.data.ki.wVk, value.data.ki.dwFlags, value.data.ki.dwExtraInfo) for value in values])
        return count if len(calls) == 1 else size
    with pytest.raises(OSError):
        mask_input(send)
    assert calls == [[(0xE8, 0, SAYDRAFT_INPUT_TAG), (0xE8, 2, SAYDRAFT_INPUT_TAG)], [(0xE8, 2, SAYDRAFT_INPUT_TAG)]]


def test_closed_owner_cannot_install_late_and_wait_parameters_are_bounded():
    hooks, api, _, _ = rig()
    assert hooks.close()
    with pytest.raises(RuntimeError):
        hooks.start()
    assert not api.trace
    for value in (True, float("nan"), -1, 31):
        with pytest.raises(ValueError):
            hooks.close(value)
    assert c.sizeof(KeyboardPacket) == (24 if c.sizeof(c.c_void_p) == 8 else 20)
    assert c.sizeof(MousePacket) == (32 if c.sizeof(c.c_void_p) == 8 else 24)


def test_close_during_blocked_startup_prevents_late_hook_installation():
    release, api = threading.Event(), API()
    def factory():
        assert release.wait(3)
        return api
    hooks = LowLevelHooks([], on_action=lambda *args: None, api_factory=factory)
    try:
        with pytest.raises(OSError):
            hooks.start(timeout=.02)
        assert not hooks.close(timeout=0)
    finally:
        release.set()
        assert hooks.close()
    assert api.trace == ["closed"]


def test_second_win32_hook_failure_removes_the_first_hook():
    removed = []
    api = Win32Hooks.__new__(Win32Hooks)
    api.thread_id, api.handles, api.callbacks, api.message, api.proc = None, [], (), None, lambda f: f
    from ctypes import wintypes as w
    api.message = w.MSG()
    api.kernel = SimpleNamespace(GetCurrentThreadId=lambda: 123, GetModuleHandleW=lambda name: 1)
    api.user = SimpleNamespace(PeekMessageW=lambda *args: 0, PostThreadMessageW=lambda *args: True,
        SetWindowsHookExW=lambda kind, *args: 55 if kind == 13 else None,
        UnhookWindowsHookEx=lambda handle: removed.append(handle) or True)
    hooks = LowLevelHooks([], on_action=lambda *args: None, api_factory=lambda: api)
    with pytest.raises(OSError):
        hooks.start()
    assert hooks.close() and removed == [55] and api.handles == []


def test_startup_snapshot_uses_physical_modifier_sides_and_logical_mouse_mapping():
    api = Win32Hooks.__new__(Win32Hooks)
    seen = []
    def key_state(vk):
        seen.append(vk)
        return 0x8000 if vk in (1, 0x11, 0xA3) else 0
    api.user = SimpleNamespace(GetSystemMetrics=lambda metric: 1, GetAsyncKeyState=key_state)
    assert api.pressed_keys() == {"right_mouse", "right_ctrl"}
    assert not {0x10, 0x11, 0x12} & set(seen)
