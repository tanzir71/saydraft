"""Scale the measured corrector across a glossary without truncating targets.

The pipeline masks its complete glossary, protected terms and literal spans
before this helper. A global phonetic index preserves ambiguity across batches;
only relevant targets are passed to the unchanged 40-term correction kernel.
"""

from functools import lru_cache

from saydraft.asr import biasing as kernel
from saydraft.dictionary.frequency import language_code


class DictionaryVocabulary:
    def __init__(self, terms):
        self.reason = None
        self._index = {}
        self._lengths = set()
        self._terms = {}
        self._encoder = None
        try:
            if sum(len(term) for term in terms) > 4 * 1024 * 1024:
                self.reason = 'vocabulary_bounds'
                return
            from metaphone import doublemetaphone
            self._encoder = lru_cache(maxsize=8192)(doublemetaphone)
            # Long/non-Latin/structured entries remain protected by the pipeline;
            # they are not safe fuzzy targets. Do not disable other valid entries.
            eligible = list(dict.fromkeys(term for term in terms if 0 < len(term) <= kernel.MAX_TERM))
            for start in range(0, len(eligible), kernel.MAX_TERMS):
                for term in eligible[start:start + kernel.MAX_TERMS]:
                    # Compile individually so conflicting case forms cannot hide
                    # other entries. The global code index keeps both ambiguous.
                    parsed = kernel.DictionaryCorrector([term])
                    for canonical, words, _signature in parsed._entries:
                        self._terms[canonical] = canonical
                        self._lengths.add(len(words))
                        for code in self._codes(canonical):
                            self._index.setdefault(code, set()).add(canonical)
        except ImportError:
            self.reason = 'phonetic_unavailable'
        except Exception:
            self.reason = 'vocabulary_unavailable'

    def _codes(self, text):
        return {code for code in self._encoder(kernel._letters(text)) if len(code) >= 2}

    def _targets(self, text):
        return set().union(*(self._index.get(code, set()) for code in self._codes(text)))

    def correct(self, text, *, language, word_set=None):
        if self.reason:
            return kernel.DictionaryResult(text, text, reason=self.reason)
        if language_code(language) != 'en' or not text or len(text) > kernel.MAX_TEXT:
            return kernel.DictionaryResult(text, text, reason='unsupported_context')
        try:
            words = kernel._tokens(text)
            active = set()
            for count in self._lengths:
                for start in range(len(words) - count + 1):
                    part = words[start:start + count]
                    if not kernel._sequence(text, part):
                        continue
                    targets = self._targets(' '.join(word.root for word in part))
                    if len(targets) == 1:
                        active.update(targets)
            proposals = {}
            active = sorted(active)
            for start in range(0, len(active), kernel.MAX_TERMS):
                engine = kernel.DictionaryCorrector(active[start:start + kernel.MAX_TERMS], phonetic=self._encoder)
                result = engine.correct(text, language=language, word_set=word_set)
                if result.reason in ('correction_unavailable', 'phonetic_unavailable', 'frequency_unavailable', 'invalid_dictionary'):
                    return kernel.DictionaryResult(text, text, reason=result.reason)
                for edit in result.edits:
                    if self._targets(edit.before) == {edit.term}:
                        proposals[edit.start, edit.end, edit.after] = edit
            edits = sorted(proposals.values(), key=lambda edit: (edit.start, edit.end, edit.after))
            conflicts = {i for i, edit in enumerate(edits) for j, other in enumerate(edits)
                         if i != j and edit.start < other.end and edit.end > other.start}
            edits = [edit for i, edit in enumerate(edits) if i not in conflicts]
            if len(edits) > kernel.MAX_EDITS:
                return kernel.DictionaryResult(text, text, reason='edit_limit')
            output = text
            for edit in reversed(edits):
                output = output[:edit.start] + edit.after + output[edit.end:]
            return kernel.DictionaryResult(text, output, tuple(edits), 'corrected' if edits else 'no_unambiguous_match')
        except Exception:
            return kernel.DictionaryResult(text, text, reason='correction_unavailable')
