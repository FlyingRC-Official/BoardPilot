from uuid import UUID

from app.models.schemas import Evidence, RetrievalCandidate


def recall_at_20(expected_chunk_ids: list[UUID], candidates: list[RetrievalCandidate]) -> float:
    if not expected_chunk_ids:
        return 1.0
    top_20 = {candidate.chunk_id for candidate in candidates if candidate.stage == "merged" and candidate.rank <= 20}
    return len(set(expected_chunk_ids) & top_20) / len(set(expected_chunk_ids))


def rerank_at_5(expected_chunk_ids: list[UUID], candidates: list[RetrievalCandidate]) -> float:
    if not expected_chunk_ids:
        return 1.0
    top_5 = {candidate.chunk_id for candidate in candidates if candidate.stage == "reranked" and candidate.rank <= 5}
    return 1.0 if set(expected_chunk_ids) & top_5 else 0.0


def citation_support_rate(evidence: list[Evidence], citation_map: dict) -> float:
    cited = {str(evidence_id) for ids in citation_map.values() for evidence_id in ids}
    valid = {str(item.id) for item in evidence}
    if not cited:
        return 0.0
    return len(cited & valid) / len(cited)
