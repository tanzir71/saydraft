"""Virtual-key names, never translated or accumulated into typed text."""

import re

MODIFIERS = {name: frozenset(("left_" + name, "right_" + name)) for name in ("ctrl", "win", "alt", "shift")}
PHYSICAL_MODIFIERS = frozenset().union(*MODIFIERS.values())
VK_NAMES = {0x01: "left_mouse", 0x02: "right_mouse", 0x04: "middle_mouse", 0x05: "xbutton1", 0x06: "xbutton2",
    0x08: "backspace", 0x09: "tab", 0x0D: "enter", 0x10: "shift", 0x11: "ctrl", 0x12: "alt", 0x13: "pause",
    0x14: "caps_lock", 0x1B: "esc", 0x20: "space", 0x21: "page_up", 0x22: "page_down", 0x23: "end",
    0x24: "home", 0x25: "left", 0x26: "up", 0x27: "right", 0x28: "down", 0x2C: "print_screen",
    0x2D: "insert", 0x2E: "delete", 0x5B: "left_win", 0x5C: "right_win", 0x5D: "apps",
    0x6A: "multiply", 0x6B: "add", 0x6C: "separator", 0x6D: "subtract", 0x6E: "decimal", 0x6F: "divide",
    0x90: "num_lock", 0x91: "scroll_lock", 0xA0: "left_shift", 0xA1: "right_shift", 0xA2: "left_ctrl",
    0xA3: "right_ctrl", 0xA4: "left_alt", 0xA5: "right_alt", 0xBA: "semicolon", 0xBB: "equal", 0xBC: "comma",
    0xBD: "minus", 0xBE: "period", 0xBF: "slash", 0xC0: "backtick", 0xDB: "left_bracket",
    0xDC: "backslash", 0xDD: "right_bracket", 0xDE: "quote"}
VK_NAMES.update({code: chr(code).lower() for code in (*range(0x30, 0x3A), *range(0x41, 0x5B))})
VK_NAMES.update({0x70 + i: f"f{i + 1}" for i in range(24)})
VK_NAMES.update({0x60 + i: f"num{i}" for i in range(10)})
ALIASES = {"control": "ctrl", "ctl": "ctrl", "windows": "win", "super": "win", "meta": "win",
    "escape": "esc", "return": "enter", "spacebar": "space", "pgup": "page_up", "pgdn": "page_down",
    "pageup": "page_up", "pagedown": "page_down", "del": "delete", "ins": "insert", "capslock": "caps_lock",
    "mouse4": "xbutton1", "mouse5": "xbutton2", "middle": "middle_mouse"}
for side in ("left", "right"):
    ALIASES.update({side + "_control": side + "_ctrl", side + "_windows": side + "_win"})
KEYS = frozenset(VK_NAMES.values()) | MODIFIERS.keys()


def normalize_key(value):
    key = re.sub(r"[\s-]+", "_", value.strip().lower())
    key = ALIASES.get(key, key)
    match = re.fullmatch(r"vk_?([0-9a-f]{2})", key)
    if match and 0 < int(match[1], 16) < 255:
        code = int(match[1], 16)
        return VK_NAMES.get(code, f"vk_{code:02x}")
    if key not in KEYS:
        raise ValueError("Unknown hotkey key name")
    return key


def physical_key(code, *, scan=0, extended=False):
    if type(code) is not int or not 0 < code < 255:
        return None
    if code == 0x10:
        return "right_shift" if scan == 0x36 else "left_shift"
    if code in (0x11, 0x12):
        return ("right_" if extended else "left_") + ("ctrl" if code == 0x11 else "alt")
    return VK_NAMES.get(code, f"vk_{code:02x}")
