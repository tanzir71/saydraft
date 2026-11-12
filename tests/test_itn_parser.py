import pytest

from saydraft.cleanup.itn import normalize_itn, parse_cardinal


@pytest.mark.parametrize("phrase,expected", [
    ("zero", 0), ("nineteen", 19), ("twenty one", 21), ("ninety-nine", 99),
    ("a hundred", 100), ("one hundred and one", 101), ("three hundred sixty five", 365),
    ("one thousand and five", 1005), ("one million two hundred thousand and five", 1200005),
    ("two lakh twenty five thousand", 225000), ("one crore two lakh", 10200000),
    ("two billion three million four thousand five", 2003004005),
    ("one trillion and five", 1000000000005),
    ("one two", None), ("twenty thirty", None), ("one hundred hundred", None),
    ("one thousand million", None), ("and two", None), ("one hundred and", None),
    ("one thousand and", None), ("one million thousand", None), ("nothing", None),
])
def test_cardinal_parser_accepts_complete_phrases_and_declines_malformed_sequences(phrase, expected):
    assert parse_cardinal(phrase) == expected



@pytest.mark.parametrize("source,expected", [
    ("send two files and three reports", "send 2 files and 3 reports"),
    ("a hundred and twenty three", "123"),
    ("one thousand five hundred", "1500"),
    ("minus five", "-5"), ("negative twenty one", "-21"),
    ("two point five", "2.5"), ("zero point zero five", "0.05"),
    ("one point twenty five", "1.25"), ("minus two point five", "-2.5"),
    ("the twenty first report", "the 21st report"), ("the hundredth item", "the 100th item"),
    ("the one hundred and third item", "the 103rd item"), ("the twelfth item", "the 12th item"),
    ("three thirty pm", "3:30 PM"), ("twelve zero five am", "12:05 AM"),
    ("eleven forty five a m", "11:45 AM"), ("three p.m.", "3 PM."),
    ("two dollars and fifty cents", "$2.50"), ("minus two dollars and five cents", "-$2.05"),
    ("three point five dollars", "$3.50"), ("five hundred euros", "€500"),
    ("three hundred taka", "৳300"), ("pay five pounds", "pay £5"),
    ("five pounds sterling", "£5"), ("weigh five pounds", "weigh 5 pounds"),
    ("twenty five percent", "25%"), ("two point five per cent", "2.5%"),
    ("March third", "March 3"), ("June twenty first", "June 21"),
    ("March third two thousand twenty six", "March 3, 2026"),
    ("March third, twenty twenty six", "March 3, 2026"),
    ("the twelfth of January", "12 January"),
    ("the third of March two thousand twenty six", "3 March, 2026"),
    ("phone zero one one two three four five six seven eight", "phone 0112345678"),
    ("call plus eight eight zero one seven one two three four five six seven eight", "call +8801712345678"),
    ("number triple five triple five triple five", "number 555555555"),
    ("phone one one one", "phone 111"),
    ("john at example dot com", "john@example.com"),
    ("john dot doe plus qa at example dot org", "john.doe+qa@example.org"),
    ("one at example dot com", "one@example.com"),
    ("look at example dot com", "look at example.com"),
    ("stop at example dot com", "stop at example.com"),
    ("email stop at example dot com", "email stop@example.com"),
    ("example dot com slash docs", "example.com/docs"),
    ("https colon slash slash example dot com slash docs", "https://example.com/docs"),
    ("http s colon slash slash example dot org", "https://example.org"),
    ("example dot co dot uk", "example.co.uk"),
    ("v two point one", "v2.1"), ("version two point one point three", "version 2.1.3"),
    ("one second", "1 second"), ("twenty second", "22nd"),
    ("apples and two oranges", "apples and 2 oranges"),
    ("one hundred and apples", "100 and apples"),
])
def test_spoken_details_render_without_guessing_missing_values(source, expected):
    assert normalize_itn(source) == expected



@pytest.mark.parametrize("source", [
    "01234", "١٢٣", "১২৩", "2026-11-12", "2.050", "__ITN_0__", "__SPAN_0__", "⟦T0⟧",
    "one two", "twenty thirty", "wait a second", "a third of the budget", "a hundredth of the total",
    "we may first review the report", "May one attend", "march two blocks", "we may one day go",
    "`version two point one`", '"three thirty pm"', "“john at example dot com”",
    "https://one.example.com/first", "one@example.com", "we used the dot product", "one.com", "foo.bar",
    "one@localhost", "বাংলা@উদাহরণ.বাংলা", "مُحمّد@مثال.اختبار", ".one.com", "--one.com",
])
def test_literals_ambiguous_phrases_existing_digits_and_entities_are_preserved(source):
    assert normalize_itn(source) == source



def test_intensity_and_prose_style_control_small_cardinals_and_ordinals():
    assert normalize_itn("two reports and the third draft", intensity=2) == "two reports and the third draft"
    assert normalize_itn("two reports and the third draft", intensity=3) == "2 reports and the 3rd draft"
    assert normalize_itn("two reports", intensity=1, style="compact") == "2 reports"
    assert normalize_itn("twenty reports", intensity=1) == "20 reports"
    for options in ({"intensity": 0}, {"intensity": True}, {"style": "unknown"}):
        with pytest.raises(ValueError):
            normalize_itn("words", **options)



def test_long_non_address_tokens_do_not_trigger_quadratic_restart_matching():
    import time

    source = "a." * 25000
    started = time.perf_counter()
    assert normalize_itn(source) == source
    assert time.perf_counter() - started < 2  # Generous regression bound; typical run is milliseconds.

