from collections import Counter

from textstats.tokenize import tokenize


def word_frequencies(text: str) -> dict[str, int]:
    return dict(Counter(tokenize(text)))


def top_words(text: str, n: int = 3) -> list[tuple[str, int]]:
    return Counter(word_frequencies(text)).most_common(n)
