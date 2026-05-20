from app.models.schemas import Evidence


def create_evidence_pack(retrieval_run_id, reranked: list[dict], limit: int = 5) -> list[Evidence]:
    evidence = []
    for rank, item in enumerate(reranked[:limit], start=1):
        chunk = item["chunk"]
        evidence.append(
            Evidence(
                retrieval_run_id=retrieval_run_id,
                chunk_id=chunk.id,
                rank=rank,
                score=item.get("rerank_score") or item.get("merged_score") or 0.0,
                quote=chunk.content[:500],
                selection_reason="Top reranked chunk selected for answer grounding.",
            )
        )
    return evidence

