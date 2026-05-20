from datetime import datetime
from typing import Any
from uuid import UUID

from app.db.store import InMemoryStore
from app.models.schemas import Chunk, Question, RetrievalCandidate, RetrievalRun
from app.retrieval.evidence import create_evidence_pack
from app.retrieval.filter_plan import build_filter_plan, high_confidence_product_id
from app.retrieval.keyword import keyword_recall
from app.retrieval.merge import merge_candidates
from app.retrieval.query_normalization import normalize_query
from app.retrieval.rerank import rerank
from app.retrieval.vector import vector_recall


def _value_matches_filter(value: Any, expected: Any) -> bool:
    if expected in (None, "", [], {}):
        return True
    if isinstance(expected, list):
        return any(_value_matches_filter(value, item) for item in expected)
    if value is None:
        return False
    if isinstance(expected, bool):
        return value == expected
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        return value == expected
    return str(value).lower() == str(expected).lower()


def _metadata_value_for_chunk(store: InMemoryStore, chunk: Chunk, field: str) -> Any:
    if field in {"product_id", "source_version_id", "chunk_id"}:
        return str(getattr(chunk, "id" if field == "chunk_id" else field))
    if hasattr(chunk, field):
        return getattr(chunk, field)
    version = store.source_versions.get(chunk.source_version_id)
    source = store.sources.get(version.source_id) if version else None
    if field == "source_id":
        return str(source.id) if source else None
    if field in {"source_type", "trust_level", "source_title", "canonical_uri"} and source:
        source_field = "title" if field == "source_title" else field
        value = getattr(source, source_field, None)
        return value.value if hasattr(value, "value") else value
    return chunk.metadata_json.get(field)


def _chunk_matches_metadata_filters(store: InMemoryStore, chunk: Chunk, filters: dict[str, Any]) -> bool:
    for field, expected in filters.items():
        if not _value_matches_filter(_metadata_value_for_chunk(store, chunk, field), expected):
            return False
    return True


def run_retrieval(store: InMemoryStore, question: Question) -> tuple[RetrievalRun, list[RetrievalCandidate], list]:
    started = datetime.utcnow()
    detected_product_id = high_confidence_product_id(question.detected_entities_json)
    detected_product_uuid = UUID(detected_product_id) if detected_product_id else None
    product_filter_id = question.product_id or detected_product_uuid
    chunks = [
        chunk
        for chunk in store.enabled_chunks(product_filter_id)
        if _chunk_matches_metadata_filters(store, chunk, question.metadata_filters_json)
    ]
    keyword_hits = keyword_recall(question.normalized_text, chunks)
    embedding_config = store.active_provider_config("embedding")
    vector_hits = vector_recall(question.normalized_text, chunks, embedding_config, store)
    merged = merge_candidates(keyword_hits, vector_hits)
    soft_boost_products = {
        item["product_id"]: item["confidence"] for item in question.detected_entities_json.get("products", [])
    }
    for item in merged:
        product_id = str(item["chunk"].product_id)
        boost = soft_boost_products.get(product_id, 0.0) * 0.15 if product_filter_id is None else 0.0
        item["soft_boost_score"] = boost
        item["merged_score"] += boost
    reranker_config = store.active_provider_config("reranker")
    reranked = rerank(question.normalized_text, merged, reranker_config)
    reranker_error = next((item.get("reranker_error", "") for item in reranked if item.get("reranker_error")), "")

    run = RetrievalRun(
        question_id=question.id,
        normalized_query=question.normalized_text,
        filter_plan_json=build_filter_plan(question.product_id, question.detected_entities_json, question.metadata_filters_json),
        retrieval_config_json={"keyword_limit": 50, "vector_limit": 50, "evidence_limit": 5},
        status="completed_with_reranker_error" if reranker_error else "completed",
        error_message=reranker_error,
    )
    run.completed_at = datetime.utcnow()
    run.latency_ms = int((run.completed_at - started).total_seconds() * 1000)
    store.add_retrieval_run(run)

    candidates: list[RetrievalCandidate] = []
    for rank, (chunk, score) in enumerate(keyword_hits, start=1):
        candidates.append(
            RetrievalCandidate(
                retrieval_run_id=run.id,
                chunk_id=chunk.id,
                stage="keyword",
                source="keyword",
                keyword_score=score,
                rank=rank,
            )
        )
    for rank, (chunk, score) in enumerate(vector_hits, start=1):
        candidates.append(
            RetrievalCandidate(
                retrieval_run_id=run.id,
                chunk_id=chunk.id,
                stage="vector",
                source="vector",
                vector_score=score,
                rank=rank,
            )
        )
    for rank, item in enumerate(merged, start=1):
        candidates.append(
            RetrievalCandidate(
                retrieval_run_id=run.id,
                chunk_id=item["chunk"].id,
                stage="merged",
                source="hybrid",
                keyword_score=item["keyword_score"],
                vector_score=item["vector_score"],
                merged_score=item["merged_score"],
                rank=rank,
                metadata_json={"deduped_chunk_ids": item.get("deduped_chunk_ids", [])},
            )
        )
    for rank, item in enumerate(reranked, start=1):
        candidates.append(
            RetrievalCandidate(
                retrieval_run_id=run.id,
                chunk_id=item["chunk"].id,
                stage="reranked",
                source=item.get("reranker_provider_name", "fake"),
                keyword_score=item["keyword_score"],
                vector_score=item["vector_score"],
                merged_score=item["merged_score"],
                rerank_score=item["rerank_score"],
                rank=rank,
                metadata_json={
                    "soft_boost_score": item.get("soft_boost_score", 0.0),
                    "deduped_chunk_ids": item.get("deduped_chunk_ids", []),
                    "reranker_model_name": item.get("reranker_model_name", "fake-overlap-reranker"),
                    "reranker_configured_provider_name": item.get("reranker_configured_provider_name", ""),
                    "reranker_error": item.get("reranker_error", ""),
                },
            )
        )
    store.add_candidates(candidates)
    evidence = store.add_evidence(create_evidence_pack(run.id, reranked))
    return run, candidates, evidence
