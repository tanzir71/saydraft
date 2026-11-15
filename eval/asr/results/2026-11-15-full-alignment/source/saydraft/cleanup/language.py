"""Language boundaries for English-specific cleanup rules."""


def english_rules_allowed(language):
    # `auto` retains the legacy text-only API. Production supplies ASR's
    # reported language (or a single pin) whenever available. Unknown language
    # is not proof of English; callers can explicitly use `und`/`mul` to retain
    # words when language evidence is unavailable or mixed.
    if type(language) is not str:
        return False
    base = language.strip().lower().replace('_', '-').split('-', 1)[0]
    return base in ('en', 'auto', '')


def transcript_language(detected, configured='auto', *, segments=()):
    """Resolve production cleanup evidence without assuming unknown speech is English.

    A single explicit language preference can supply the missing evidence.
    Mixed/unknown background segments keep conservative cleanup for the whole
    joined transcript, rather than trusting only the final segment's language.
    """
    from saydraft.asr.languages import WHISPER_LANGUAGES
    def code(value):
        if type(value) is not str:
            return ''
        base = value.strip().lower().replace('_', '-').split('-', 1)[0]
        return base if base in WHISPER_LANGUAGES or base in ('und', 'mul') else ''
    preference = code(configured)
    def resolve(value):
        return code(value) or preference or 'und'
    if segments:
        languages = {resolve(value) for value in segments}
        if len(languages) == 1:
            return languages.pop()
        return 'und' if 'und' in languages else 'mul'
    return resolve(detected)
