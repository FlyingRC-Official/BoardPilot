from math import sqrt
from typing import Iterable

from app.providers.embedding import embedding_provider


def cosine(a: list[float], b: list[float]) -> float:
    denom = (sqrt(sum(x * x for x in a)) * sqrt(sum(x * x for x in b))) or 1.0
    return sum(x * y for x, y in zip(a, b)) / denom


def vector_recall(query: str, chunks: Iterable) -> list[tuple[object, float]]:
    query_vector = embedding_provider.embed(query).vector
    scored = []
    for chunk in chunks:
        vector = embedding_provider.embed(chunk.content).vector
        scored.append((chunk, cosine(query_vector, vector)))
    return sorted(scored, key=lambda item: item[1], reverse=True)[:50]

