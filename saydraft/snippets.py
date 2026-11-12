"""Bounded snippet documents and one-pass local variables."""

from datetime import datetime
from collections import Counter
import json
import re
import unicodedata

MAX_BYTES = 4 * 1024 * 1024
MAX_ENTRIES = 2048
MAX_TRIGGER = 256
MAX_EXPANSION = 65536
# A receipt for adopting the existing v2 table as the live snippet store.
CANONICAL_SOURCE = "saydraft:snippets-canonical-v1"
_VARIABLE = re.compile(r"\{\{(?:date|clipboard)\}\}|\{(date|clipboard)\}")


def trigger_key(value):
    return unicodedata.normalize("NFC", value).casefold()


def validate_entries(entries):
    if not isinstance(entries, dict) or len(entries) > MAX_ENTRIES:
        raise ValueError(f"Snippets must be an object with at most {MAX_ENTRIES} entries.")
    keys = set()
    for trigger, expansion in entries.items():
        if (not isinstance(trigger, str) or not trigger.strip() or trigger != trigger.strip()
                or len(trigger) > MAX_TRIGGER or any(c in trigger for c in "\r\n\0")):
            raise ValueError(f"Snippet triggers must be nonempty phrases of at most {MAX_TRIGGER} characters.")
        key = trigger_key(trigger)
        if key in keys:
            raise ValueError("Snippet trigger phrases must be unique, ignoring case and Unicode normalization.")
        keys.add(key)
        if not isinstance(expansion, str) or len(expansion) > MAX_EXPANSION or "\0" in expansion:
            raise ValueError(f"Snippet expansions must be text of at most {MAX_EXPANSION} characters without NUL.")
    try:
        if len((json.dumps(entries, ensure_ascii=False, indent=2) + "\n").encode("utf-8")) > MAX_BYTES:
            raise ValueError("Snippets exceed the 4 MB editing limit.")
    except UnicodeError as exc:
        raise ValueError("Snippets contain invalid Unicode text.") from exc
    return entries


def parse_document(text, *, strict=False):
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Snippets exceed the 4 MB editing limit.")
    if text.lstrip().startswith("{"):
        try:
            data = json.loads(text)
        except (ValueError, RecursionError) as exc:
            # Legacy triggers could begin with a literal brace, e.g. {name}=… .
            if not re.match(r"^\s*\{[^{}\r\n]*\}[^=\r\n]*=", text):
                raise ValueError("Snippet JSON could not be read.") from exc
        else:
            return validate_entries(data)
    # Retain the old file's comments/ignored lines and last-duplicate-wins rule.
    entries, spelling = {}, {}
    for line in text.splitlines():
        if strict and line.strip() and not line.lstrip().startswith("#") and "=" not in line:
            raise ValueError("Legacy snippet lines need trigger=expansion; multiline expansions use JSON.")
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            trigger, expansion = (part.strip() for part in line.split("=", 1))
            if trigger:
                key = trigger_key(trigger)
                if key in spelling:
                    entries.pop(spelling[key])
                entries[trigger], spelling[key] = expansion, trigger
    return validate_entries(entries)


def dump_document(entries):
    return json.dumps(validate_entries(entries), ensure_ascii=False, indent=2) + "\n"


def variables(template):
    return {m[1] for m in _VARIABLE.finditer(template) if m[1]}


def render_variables(template, *, date=None, clipboard=None):
    if not isinstance(template, str) or len(template) > MAX_EXPANSION:
        raise ValueError("Snippet template exceeds its text limit.")
    def replace(match):
        if match[0].startswith("{{"):
            return match[0][1:-1]
        if match[1] == "date":
            return (date or datetime.now().date()).isoformat()
        if clipboard is None:
            raise ValueError("Clipboard text is unavailable; the spoken trigger is kept.")
        return clipboard
    if clipboard is not None and (not isinstance(clipboard, str) or len(clipboard) > MAX_EXPANSION or "\0" in clipboard):
        raise ValueError("Clipboard text exceeds the snippet limit or is invalid.")
    parts, size, position = [], 0, 0
    def append(value):
        nonlocal size
        size += len(value)
        if size > MAX_EXPANSION:
            raise ValueError("Expanded snippet exceeds its text limit; the spoken trigger is kept.")
        parts.append(value)
    for match in _VARIABLE.finditer(template):
        append(template[position:match.start()])
        append(replace(match))
        position = match.end()
    append(template[position:])
    value = "".join(parts)
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise ValueError("Expanded snippet contains invalid Unicode text.") from exc
    return value


def resolve_mapping(text, mapping, originals, *, clipboard_reader=None, date=None):
    """Resolve used opaque values once; substitutions never become templates."""
    output, failed = {}, False
    used = Counter(re.findall(r"__SPAN_\d+__", text))
    result_size = len(text.encode("utf-8"))
    cache, needs_clipboard = {}, {}
    clipboard, clipboard_attempted, clipboard_available = None, False, False
    date = date or datetime.now().date()
    for token, template in mapping.items():
        occurrences = used[token]
        if not occurrences:
            continue
        try:
            if template not in needs_clipboard:
                needs_clipboard[template] = "clipboard" in variables(template)
            if needs_clipboard[template]:
                if not clipboard_attempted:
                    clipboard_attempted = True
                    if clipboard_reader is not None:
                        try:
                            clipboard = clipboard_reader()
                            clipboard_available = isinstance(clipboard, str)
                        except Exception:
                            pass  # Do not log contents or provider errors.
                if not clipboard_available:
                    raise ValueError("Clipboard unavailable")
            value, size = cache.get(template, (None, 0))
            if value is None:
                value = render_variables(template, date=date, clipboard=clipboard)
                size = len(value.encode("utf-8"))
            delta = occurrences * (size - len(token))
            if result_size + delta > MAX_BYTES:
                raise ValueError("Snippet result exceeds its total byte limit")
            result_size += delta
            cache[template] = value, size
            output[token] = value
        except ValueError:
            output[token], failed = originals.get(token, token), True
            result_size += occurrences * (len(output[token].encode("utf-8")) - len(token))
    return output, failed
