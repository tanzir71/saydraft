"""Language codes supported by the pinned faster-whisper 1.2.1 tokenizer."""

# https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/faster_whisper/tokenizer.py

WHISPER_LANGUAGES = frozenset("""
af am ar as az ba be bg bn bo br bs ca cs cy da de el en es et eu fa fi fo fr gl
gu ha haw he hi hr ht hu hy id is it ja jw ka kk km kn ko la lb ln lo lt lv mg mi
mk ml mn mr ms mt my ne nl nn no oc pa pl ps pt ro ru sa sd si sk sl sn so sq sr
su sv sw ta te tg th tk tl tr tt uk ur uz vi yi yo zh yue
""".split())

PARAKEET_LANGUAGES = frozenset("""
bg hr cs da nl en et fi fr de el hu it lv lt mt pl pt ro sk sl es sv ru uk
""".split())


def normalize_pins(values):
    pins = tuple(dict.fromkeys(str(value).strip().lower() for value in values if value))
    if len(pins) > 3:
        raise ValueError("Choose Auto or at most three languages")
    if any(value not in WHISPER_LANGUAGES for value in pins):
        raise ValueError("Unsupported language code")
    return pins
