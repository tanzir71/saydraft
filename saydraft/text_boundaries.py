"""Unicode word edges shared by glossary protection and validation."""

import unicodedata


def _word_character(char):
    return char == "_" or char.isalnum() or unicodedata.category(char).startswith("M")


def whole_word_match(text, match):
    return ((match.start() == 0 or not _word_character(text[match.start() - 1]))
            and (match.end() == len(text) or not _word_character(text[match.end()])))
