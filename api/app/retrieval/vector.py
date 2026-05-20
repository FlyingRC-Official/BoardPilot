from math import sqrt
from typing import Iterable

from app.providers.embedding import embedding_provider, run_configured_embedding


def cosine(a: list[float], b: list[float]) -> float:
    denom = (sqrt(sum(x * x for x in a)) * sqrt(sum(x * x for x in b))) or 1.0
    return sum(x * y for x, y in zip(a, b)) / denom


def _embedding_identity(provider_config) -> tuple[str, str]:
    if provider_config:
        return provider_config.provider_name, provider_config.model_name
    return embedding_provider.provider_name, embedding_provider.model_name


def _stored_vector(store, chunk_id, provider_config) -> list[float]:
    if not store:
        return []
    provider_name, model_name = _embedding_identity(provider_config)
    for embedding in store.embeddings_for_chunk(chunk_id):
        if embedding.provider_name == provider_name and embedding.model_name == model_name:
            return embedding.vector
    return []


def vector_recall(query: str, chunks: Iterable, provider_config=None, store=None) -> list[tuple[object, float]]:
    query_embedding = run_configured_embedding(provider_config, query)
    if query_embedding.error_message or not query_embedding.vector:
        return []
    query_vector = query_embedding.vector
    scored = []
    for chunk in chunks:
        vector = _stored_vector(store, chunk.id, provider_config)
        if not vector and provider_config and provider_config.provider_name != embedding_provider.provider_name:
            continue
        if not vector:
            vector = run_configured_embedding(provider_config, chunk.content).vector
        scored.append((chunk, cosine(query_vector, vector)))
    return sorted(scored, key=lambda item: item[1], reverse=True)[:50]
