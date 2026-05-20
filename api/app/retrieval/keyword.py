from collections import Counter
from typing import Iterable

from app.providers.fake import tokenize


def keyword_score(query: str, text: str) -> float:
    q = Counter(tokenize(query))
    d = Counter(tokenize(text))
    if not q:
        return 0.0
    overlap = sum(min(q[token], d[token]) for token in q)
    exact_bonus = sum(1 for token in q if token in d and any(ch.isdigit() for ch in token))
    return (overlap + exact_bonus) / len(q)


def keyword_recall(query: str, chunks: Iterable) -> list[tuple[object, float]]:
    scored = [(chunk, keyword_score(query, chunk.content)) for chunk in chunks]
    return sorted([item for item in scored if item[1] > 0], key=lambda item: item[1], reverse=True)[:50]

