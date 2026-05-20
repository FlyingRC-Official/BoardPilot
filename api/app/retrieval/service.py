from datetime import datetime

from app.db.store import InMemoryStore
from app.models.schemas import Question, RetrievalCandidate, RetrievalRun
from app.retrieval.evidence import create_evidence_pack
from app.retrieval.filter_plan import build_filter_plan
from app.retrieval.keyword import keyword_recall
from app.retrieval.merge import merge_candidates
from app.retrieval.query_normalization import normalize_query
from app.retrieval.rerank import rerank
from app.retrieval.vector import vector_recall


def run_retrieval(store: InMemoryStore, question: Question) -> tuple[RetrievalRun, list[RetrievalCandidate], list]:
    started = datetime.utcnow()
    chunks = store.enabled_chunks(question.product_id)
    keyword_hits = keyword_recall(question.normalized_text, chunks)
    vector_hits = vector_recall(question.normalized_text, chunks)
    merged = merge_candidates(keyword_hits, vector_hits)
    reranked = rerank(question.normalized_text, merged)

    run = RetrievalRun(
        question_id=question.id,
        normalized_query=question.normalized_text,
        filter_plan_json=build_filter_plan(question.product_id),
        retrieval_config_json={"keyword_limit": 50, "vector_limit": 50, "evidence_limit": 5},
    )
    run.completed_at = datetime.utcnow()
    run.latency_ms = int((run.completed_at - started).total_seconds() * 1000)
    store.add_retrieval_run(run)

    candidates: list[RetrievalCandidate] = []
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
            )
        )
    for rank, item in enumerate(reranked, start=1):
        candidates.append(
            RetrievalCandidate(
                retrieval_run_id=run.id,
                chunk_id=item["chunk"].id,
                stage="reranked",
                source="fake_reranker",
                keyword_score=item["keyword_score"],
                vector_score=item["vector_score"],
                merged_score=item["merged_score"],
                rerank_score=item["rerank_score"],
                rank=rank,
            )
        )
    store.add_candidates(candidates)
    evidence = store.add_evidence(create_evidence_pack(run.id, reranked))
    return run, candidates, evidence

