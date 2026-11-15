from textstats.frequency import word_frequencies


def test_more_punctuation():
    assert word_frequencies("Hello, world! hello?") == {"hello": 2, "world": 1}


def test_apostrophes_kept():
    assert word_frequencies("Don't stop") == {"don't": 1, "stop": 1}
