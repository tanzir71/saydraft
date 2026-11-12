import pytest

from saydraft.dictionary.alignment import _soundex, suggest_correction


def uncommon(*args):
    return False


@pytest.mark.parametrize("before,after,term,reason", [
    ("Use Kubernetis here.", "Use Kubernetes here.", "Kubernetes", "spelling"),
    ("Saydrfat is ready.", "Saydraft is ready.", "Saydraft", "spelling"),
    ("Use Saydrfat-pro.", "Use Saydraft-pro.", "Saydraft-pro", "spelling"),
    ("Ask Jon now.", "Ask John now.", "John", "spelling"),
    ("Meet Smith.", "Meet Smythe.", "Smythe", "phonetic"),
    ("Meet Washington.", "Meet Woshengten.", "Woshengten", "phonetic"),
    ("Meet Steven.", "Meet Stephen.", "Stephen", "spelling"),
    ("Meet O'Conor.", "Meet O'Connor.", "O'Connor", "spelling"),
    ("Use kubernetes.", "Use Kubernetes.", "Kubernetes", "capitalization"),
    ("Use iphone.", "Use iPhone.", "iPhone", "capitalization"),
])
def test_one_close_uncommon_word_returns_exact_spelling_and_span(before, after, term, reason):
    result = suggest_correction(before, after, "en", common_check=uncommon)
    assert result is not None
    assert result.term == term and result.reason == reason
    assert before[result.original_start:result.original_end] == result.original
    assert after[result.current_start:result.current_end] == term


def test_bundled_filter_allows_kubernetes_but_refuses_ordinary_word_edits():
    assert suggest_correction("Use Kubernetis.", "Use Kubernetes.", "en").term == "Kubernetes"
    assert suggest_correction("Use form here.", "Use from here.", "en") is None
    assert suggest_correction("Use kubernetes.", "Use Kubernetes.", "en").reason == "capitalization"
    assert suggest_correction("Use iphone.", "Use iPhone.", "en").term == "iPhone"


@pytest.mark.parametrize("language,before,after,term", [
    ("bn-BD", "নাম কুবেরনেটিস হবে।", "নাম কুবারনেটিস হবে।", "কুবারনেটিস"),
    ("ar", "استخدم كوبرنيتس هنا.", "استخدم كوبرنيتيس هنا.", "كوبرنيتيس"),
    ("de", "Nutze Saydrfat.", "Nutze Saydraft.", "Saydraft"),
])
def test_spaced_scripts_keep_the_users_written_form(language, before, after, term):
    result = suggest_correction(before, after, language)
    assert result is not None and result.term == term
    assert after[result.current_start:result.current_end] == term


def test_unicode_normalization_is_not_a_correction_and_offsets_stay_in_raw_input():
    assert suggest_correction("Use café.", "Use cafe\u0301.", "en", common_check=uncommon) is None
    result = suggest_correction("Use Cafe.", "Use Cafe\u0301.", "en", common_check=uncommon)
    assert result.term == "Café"
    assert result.current_start == 4 and result.current_end == 9


@pytest.mark.parametrize("before,after", [
    ("Use Kubernetis.", "Use Kubernetes now."),  # insertion
    ("Use Kubernetis now.", "Use Kubernetes."),  # deletion
    ("Use Kubernetis tool.", "Try Kubernetes tool."),  # multiple words
    ("Use Kubernetis.", "Use Kubernetes!"),  # punctuation also changed
    ("Use Kubernetis.", "Use  Kubernetes."),  # whitespace also changed
    ("Use Kubernetis.", "Use Kub ernetes."),  # split word
    ("Use Kuber netis.", "Use Kubernetes."),  # merged word
    ("Use Kubernetis.", "Use Spreadsheet."),  # distant rewrite
    ("the report", "THE report"),  # emphasis
    ("hello world", "Hello world"),  # common sentence case
    ("thanks Bob", "Thanks Bob"),
    ("hello world", "hELLO world"),
    ("hello world", "HellO world"),
    ("hello world", "hEllo world"),
    ("the report", "tHe report"),
    ("Use apple.", "Use Apple."),  # common capitalization is ambiguous
    ("Use Kubernetes.", "Use KUBERNETES."),
    ("Use AB.", "Use AC."),  # short tokens
    ("Use x0.", "Use x1."),  # numbers
    ("Use Kubernetis42.", "Use Kubernetes42."),
    ("Use Kubernetis_id.", "Use Kubernetes_id."),
    ("Use Kubernetis-2.", "Use Kubernetes-2."),
    ("Use #Kubernetis.", "Use #Kubernetes."),
    ("Use \u202eKubernetis.", "Use \u202eKubernetes."),
    ("Use /Kubernetis.", "Use /Kubernetes."),
    ("Use `Kubernetis`.", "Use `Kubernetes`."),
    ('Use "Kubernetis".', 'Use "Kubernetes".'),
    ("Use “Kubernetis”.", "Use “Kubernetes”."),
    ("Use Kubernetis@example.org.", "Use Kubernetes@example.org."),
    ("Use https://host/Kubernetis.", "Use https://host/Kubernetes."),
    ("Use Kubernetis.example.", "Use Kubernetes.example."),
    ("Use Kubernetis.", "Use Kubernetеs."),  # Cyrillic e in Latin name
    ("Use Москва.", "Use Москвa."),  # Latin a in Cyrillic name
    ("Use Straße.", "Use STRASSE."),  # casefold expansion
    ("", "Kubernetes"), ("Kubernetis", ""),
    ("Kubernetis", "Kubernetis"),
])
def test_rewrites_literals_case_ambiguity_and_confusables_do_not_learn(before, after):
    assert suggest_correction(before, after, "en") is None


def test_known_proper_term_can_supply_capitalization_evidence():
    assert suggest_correction("Use apple.", "Use Apple.", "en", known_terms=("Apple",)).term == "Apple"
    assert suggest_correction("Use nasa.", "Use NASA.", "en", known_terms=("NASA",)).term == "NASA"
    assert suggest_correction("Use ebay.", "Use eBay.", "en").term == "eBay"


@pytest.mark.parametrize("language", ["auto", "xx", "", None, "ja", "zh-CN", "ko", "th"])
def test_unavailable_or_unsegmented_language_declines(language):
    assert suggest_correction("Use Kubernetis.", "Use Kubernetes.", language) is None


def test_missing_frequency_data_declines_even_known_capitalization():
    assert suggest_correction("Use apple.", "Use Apple.", "en", known_terms=("Apple",),
        common_check=lambda *args: None) is None


def test_phonetics_are_english_only_and_not_a_license_for_distant_substitutions():
    assert suggest_correction("Meet Smith.", "Meet Smythe.", "de", common_check=uncommon) is None
    assert suggest_correction("Meet Washington.", "Meet Wozniacki.", "en", common_check=uncommon) is None


@pytest.mark.parametrize("before,after", [
    ("x" * 4097, "y" * 4097), ("Use " + "a" * 65, "Use " + "a" * 64 + "b"),
    ("a " * 513 + "Kubernetis", "a " * 513 + "Kubernetes"),
])
def test_oversized_input_declines_before_frequency_lookup(before, after):
    def unexpected_lookup(*args):
        pytest.fail("oversized input reached the word filter")
    assert suggest_correction(before, after, "en", common_check=unexpected_lookup) is None


def test_known_term_scan_is_bounded_even_for_an_endless_source():
    def terms():
        for _ in range(1024):
            yield "other"
        pytest.fail("known-term input was not bounded")
    assert suggest_correction("Use apple.", "Use Apple.", "en", known_terms=terms()) is None


@pytest.mark.parametrize("original,term,language", [
    ("كوبرنيتيس", "كـوبرنيتيس", "ar"),
    ("كوبرنيتيس", "كُوبرنيتيس", "ar"),
    ("O'Conor", "O’Conor", "en"),
])
def test_lookup_equivalent_presentation_changes_do_not_become_words(original, term, language):
    assert suggest_correction(original, term, language, common_check=uncommon) is None


def test_maximum_word_and_token_counts_are_still_eligible():
    result = suggest_correction("a" * 64, "a" * 63 + "b", "en", common_check=uncommon)
    assert result is not None and len(result.term) == 64
    assert suggest_correction("a " * 511 + "Kubernetis", "a " * 511 + "Kubernetes", "en") is not None


@pytest.mark.parametrize("name,code", [
    ("Washington", "W252"), ("Pfister", "P236"), ("Jackson", "J250"),
    ("Tymczak", "T522"), ("Gutierrez", "G362"), ("Ashcraft", "A261"),
])
def test_phonetic_codes_match_national_archives_independent_examples(name, code):
    assert _soundex(name) == code
