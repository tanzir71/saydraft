import pytest

from saydraft.insert.sendinput import KEYEVENTF_KEYUP, KEYEVENTF_UNICODE, type_unicode, unicode_events


def test_unicode_input_preserves_all_utf16_units_for_bengali_arabic_and_emoji():
    text = "Hello from Voice Tree. বাংলা العربية 🙂"
    encoded = text.encode("utf-16-le")
    expected = [int.from_bytes(encoded[index:index + 2], "little") for index in range(0, len(encoded), 2)]
    events = unicode_events(text)
    assert [event.data.ki.wScan for event in events[::2]] == expected
    assert [event.data.ki.wScan for event in events[1::2]] == expected
    assert all(event.data.ki.wVk == 0 for event in events)
    assert all(event.data.ki.dwFlags == KEYEVENTF_UNICODE for event in events[::2])
    assert all(event.data.ki.dwFlags == KEYEVENTF_UNICODE | KEYEVENTF_KEYUP for event in events[1::2])


def test_input_rejects_partial_os_delivery_instead_of_claiming_success():
    with pytest.raises(OSError, match="only 1 of"):
        type_unicode("hello", sender=lambda count, inputs, size: 1)


def test_long_text_is_batched_with_complete_press_release_pairs():
    batches = []

    def sender(count, inputs, size):
        batches.append(count)
        assert count % 2 == 0
        return count

    type_unicode("a" * 300, sender=sender)
    assert batches == [256, 256, 88]


def test_enter_uses_a_return_press_release_pair_and_releases_partial_delivery_without_repressing():
    from saydraft.insert.sendinput import press_enter

    batches = []
    def sender(count, inputs, size):
        batches.append([(event.data.ki.wVk, event.data.ki.dwFlags) for event in inputs])
        return count
    press_enter(sender=sender)
    assert batches == [[(0x0D, 0), (0x0D, KEYEVENTF_KEYUP)]]
    batches.clear()
    def partial(count, inputs, size):
        sender(count, inputs, size)
        return 1
    with pytest.raises(OSError, match="only 1 of 2"):
        press_enter(sender=partial)
    assert batches == [[(0x0D, 0), (0x0D, KEYEVENTF_KEYUP)], [(0x0D, KEYEVENTF_KEYUP)]]
