"""Offline TF-IDF baseline, not a multilingual/semantic embedding model.

Fit only on corpus text, never evaluation questions or expected labels. Create
a new provider/index when the corpus changes. This baseline makes retrieval
evaluation reproducible without passing an answer key to a fake provider.
"""

from collections import Counter
import math
import re
import unicodedata


def _terms(text: str) -> Counter[str]:
    text = unicodedata.normalize("NFD", text.casefold().replace("đ", "d"))
    text = "".join(char for char in text if not unicodedata.combining(char))
    words = re.findall(r"[^\W_]+", text)
    return Counter(words + [f"bigram:{a} {b}" for a, b in zip(words, words[1:])])


class LexicalEmbeddingProvider:
    def __init__(self, corpus: list[str]) -> None:
        if not isinstance(corpus, list) or any(not isinstance(text, str) or not text.strip() for text in corpus):
            raise ValueError("corpus must be a list of non-blank texts")
        frequency = Counter(term for text in corpus for term in _terms(text))
        self._positions = {term: index for index, term in enumerate(sorted(frequency), start=1)}
        self._idf = (1.0,) + tuple(
            math.log((len(corpus) + 1) / (frequency[term] + 1)) + 1
            for term in sorted(frequency)
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not isinstance(texts, list):
            raise ValueError("texts must be a list")
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        if not isinstance(text, str) or not text.strip():
            raise ValueError("text must be non-blank")
        vector = [0.0] * len(self._idf)
        for term, count in _terms(text).items():
            index = self._positions.get(term, 0)
            vector[index] += (1 + math.log(count)) * self._idf[index]
        if not any(vector):
            vector[0] = 1.0
        return vector
