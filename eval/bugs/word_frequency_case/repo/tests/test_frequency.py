from textstats.frequency import top_words, word_frequencies


def test_simple_counts():
    assert word_frequencies("a b a") == {"a": 2, "b": 1}


def test_case_and_punctuation_ignored():
    freqs = word_frequencies("The cat. the end. The END")
    assert freqs == {"the": 3, "cat": 1, "end": 2}
    assert top_words("The cat. the end. The END", 1) == [("the", 3)]
