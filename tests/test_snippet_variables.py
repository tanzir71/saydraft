from datetime import date
import ctypes as ct
from types import SimpleNamespace

import pytest

from saydraft.core.interfaces import TargetContext
from saydraft.insert.clipboard_handles import ClipboardHandles, ClipboardUnavailable
from saydraft.insert.clipboard_win import WindowsClipboard
from saydraft.snippets import render_variables, resolve_mapping
from tests.test_processing import make_processor, process
from tests.test_clipboard_transactions import Api


def test_variables_are_one_pass_with_literal_braces_and_unknown_names_preserved():
    assert render_variables("{date} {clipboard} {{date}} {unknown} {{unknown}}", date=date(2026, 11, 13),
        clipboard="sig {date} \\1") == "2026-11-13 sig {date} \\1 {date} {unknown} {{unknown}}"
    calls = []
    output, failed = resolve_mapping("__SPAN_0__ __SPAN_1__", {"__SPAN_0__": "{clipboard}", "__SPAN_1__": "{clipboard} {date}", "__SPAN_2__": "{clipboard}"},
        {}, date=date(2026, 11, 13), clipboard_reader=lambda: calls.append(1) or "{date}")
    assert output == {"__SPAN_0__": "{date}", "__SPAN_1__": "{date} 2026-11-13"} and not failed and calls == [1]
    assert resolve_mapping("plain", {"__SPAN_0__": "{clipboard}"}, {}, clipboard_reader=lambda: pytest.fail("Unused read")) == ({}, False)


def test_regex_case_variants_use_the_selected_trigger_key_without_a_lookup_failure():
    from saydraft.core.preferences import protect_snippets, restore_snippets
    protected, mapping = protect_snippets("İ", {"i": "Public value"})
    assert restore_snippets(protected, mapping) == "Public value"


def test_unicode_trigger_spelling_is_retained_and_equivalent_forms_match_without_rewriting_other_text():
    from saydraft.core.preferences import expand_snippets, parse_snippets
    entries = parse_snippets('Café=Cafe value\nStraße=Street value\n')
    assert entries == {"Café": "Cafe value", "Straße": "Street value"}
    text = "Café CAFE\u0301 cafe\u0301 Straße STRASSE caféteria Cafe\u0301teria"
    assert expand_snippets(text, entries) == "Cafe value Cafe value Cafe value Street value Street value caféteria Cafe\u0301teria"


def test_real_processor_keeps_values_out_of_cleanup_and_saves_expanded_history_before_insertion():
    seen, reads = [], []
    processor, events, _ = make_processor(cleaner=SimpleNamespace(process_transcript=lambda text, context: seen.append(text) or text))
    processor.snippets = {"signature": "{date}\n{clipboard}", "other": "Should not recurse"}
    processor.snippet_date = lambda: date(2026, 11, 13)
    processor.snippet_clipboard = lambda: reads.append(1) or "other {date} \\1 বাংলা العربية"
    result = process(processor, "signature signature")
    value = "2026-11-13\nother {date} \\1 বাংলা العربية"
    assert result.cleaned_text == value + " " + value and reads == [1]
    assert seen == ["__SPAN_0__ __SPAN_1__"]
    assert [event[0] for event in events] == ["history", "insert"]
    assert events[0][1].raw_text == "signature signature" and events[0][1].cleaned_text == result.cleaned_text
    assert events[1][1] == result.cleaned_text


@pytest.mark.parametrize("options", [dict(insert_text=False), dict(target=TargetContext("owned", is_password=True)),
    dict(target=TargetContext("owned", uia_status="unavailable")), dict(enter_guard=lambda: False),
    dict(field_guard=lambda: "password_field")])
def test_unavailable_or_cancelled_fields_and_history_only_do_not_read_clipboard(options):
    processor, _, messages = make_processor(cleaner=SimpleNamespace(process_transcript=lambda text, context: text))
    processor.snippets = {"clip": "{clipboard}", "day": "{date}"}
    processor.snippet_date = lambda: date(2026, 11, 13)
    processor.snippet_clipboard = lambda: pytest.fail("Private clipboard must not be read")
    result = process(processor, "clip day", **options)
    assert result.cleaned_text == "clip 2026-11-13" and len(messages) >= 1


@pytest.mark.parametrize("value", [None, "x" * 65537, "a\0b", "\ud800"], ids=["missing", "oversized", "nul", "unicode"])
def test_bad_clipboard_values_keep_the_spoken_trigger_and_notify_without_values(value):
    processor, _, messages = make_processor(cleaner=SimpleNamespace(process_transcript=lambda text, context: text))
    processor.snippets = {"clip": "{clipboard}"}
    processor.snippet_clipboard = lambda: value
    assert process(processor, "clip").cleaned_text == "clip"
    assert messages == ["Some snippet expansions exceeded the limit or were unavailable; their spoken triggers were kept."]


def test_repeated_clipboard_variables_are_bounded_before_allocation_and_total_result_keeps_overflow_triggers():
    from saydraft.core.preferences import protect_snippets, restore_snippets
    from saydraft.snippets import MAX_BYTES
    clipboard = "x" * 65536
    with pytest.raises(ValueError, match="text limit"):
        render_variables("{clipboard}" * 3000, clipboard=clipboard)
    originals = {}
    protected, mapping = protect_snippets("clip " * 100, {"clip": "{clipboard}"}, originals=originals)
    mapping, failed = resolve_mapping(protected, mapping, originals, clipboard_reader=lambda: clipboard)
    output = restore_snippets(protected, mapping)
    assert failed and len(output.encode("utf-8")) <= MAX_BYTES
    words = output.split()
    assert len(words) == 100 and words.count("clip") > 0
    assert all(word in ("clip", clipboard) for word in words)


def test_feedback_failure_cannot_leave_opaque_tokens_in_history_or_interrupt_processing():
    processor, events, _ = make_processor(cleaner=SimpleNamespace(process_transcript=lambda text, context: text))
    processor.snippets = {"clip": "{clipboard}"}
    def unavailable(message):
        raise RuntimeError("fixture feedback port unavailable")
    processor.notify = unavailable
    result = process(processor, "clip")
    assert result.cleaned_text == "clip" and events[0][1].cleaned_text == "clip"
    assert [event[0] for event in events] == ["history", "insert"]


def test_clipboard_native_text_decoder_reads_only_owned_memory_and_never_frees_it():
    raw = ("বাংলা العربية 🙂\r\n" + "\0").encode("utf-16-le")
    buffer = ct.create_string_buffer(raw)
    unlocked = []
    api = ClipboardHandles.__new__(ClipboardHandles)
    api.kernel = SimpleNamespace(GlobalSize=lambda handle: len(raw), GlobalLock=lambda handle: ct.addressof(buffer),
        GlobalUnlock=lambda handle: unlocked.append(handle))
    assert api.unicode_text(123) == "বাংলা العربية 🙂\r\n" and unlocked == [123]
    api.kernel.GlobalSize = lambda handle: 200000
    with pytest.raises(ClipboardUnavailable):
        api.unicode_text(123)
    assert unlocked == [123]
    api.kernel.GlobalSize = lambda handle: 2
    # First UTF-16 code unit is not a terminator; bounds stay inside our buffer.
    with pytest.raises(ClipboardUnavailable):
        api.unicode_text(123)
    assert unlocked == [123, 123]


def test_clipboard_read_is_nonmutating_and_refuses_pending_recovery():
    api = Api()
    api.unicode_text = lambda handle: "Public sample"
    clipboard = WindowsClipboard(api_factory=lambda: api)
    before = (list(api.clip), api.serial, api.owner_id, dict(api.heap))
    assert clipboard.read_text() == "Public sample"
    assert (api.clip, api.serial, api.owner_id, api.heap) == before
    assert not api.windows and api.open_window is None and not api.events
    clipboard.pending = object()
    with pytest.raises(ClipboardUnavailable):
        clipboard.read_text()
