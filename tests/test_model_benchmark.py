from tools.bench_models import normalized, score


def test_scoring_handles_word_edits_and_retains_combining_marks():
    assert normalized("হ্যালো, বিশ্ব!") == "হ্যালো বিশ্ব"
    assert normalized("مَرْحَبًا، بالعالم!") == "مَرْحَبًا بالعالم"
    assert score("Hello, from Saydraft.", "hello Saydraft") == {
        "word_errors": 1, "reference_words": 3, "character_errors": 4, "reference_characters": 17}
    assert score("go go", "go")["word_errors"] == 1
