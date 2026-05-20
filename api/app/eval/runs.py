from statistics import mean
from typing import Optional

from app.answers.service import generate_answer
from app.db.store import InMemoryStore
from app.eval.metrics import citation_support_rate, recall_at_20, rerank_at_5
from app.models.schemas import EvalResult, EvalRun, EvidenceSufficiency, FailureCategory, Question
from app.retrieval.query_normalization import normalize_query
from app.retrieval.service import run_retrieval


def categorize_eval_failure(
    recall: float,
    rerank: float,
    evidence_sufficiency: EvidenceSufficiency,
    citation_support: float,
) -> Optional[FailureCategory]:
    if recall < 1.0:
        return FailureCategory.bad_vector_recall
    if rerank < 1.0:
        return FailureCategory.bad_rerank
    if evidence_sufficiency != EvidenceSufficiency.sufficient:
        return FailureCategory.insufficient_evidence
    if citation_support < 1.0:
        return FailureCategory.unsupported_claim
    return None


def run_eval_batch(store: InMemoryStore, name: str = "MVP eval") -> tuple[EvalRun, list[EvalResult]]:
    run = EvalRun(name=name, provider_config_json=store.provider_config_snapshot())
    results: list[EvalResult] = []
    for case in [case for case in store.eval_cases.values() if case.active]:
        question = store.add_question(
            Question(product_id=case.product_id, raw_text=case.question_text, normalized_text=normalize_query(case.question_text))
        )
        retrieval_run, candidates, evidence = run_retrieval(store, question)
        answer = generate_answer(store, question, retrieval_run.id, evidence)
        reranked = [candidate for candidate in candidates if candidate.stage == "reranked"]
        recall = recall_at_20(case.expected_chunk_ids_json, candidates)
        rerank = rerank_at_5(case.expected_chunk_ids_json, reranked)
        support = citation_support_rate(evidence, answer.citation_map_json)
        failure_category = categorize_eval_failure(recall, rerank, answer.evidence_sufficiency, support)
        need_review = failure_category is not None
        result = store.add_eval_result(
            EvalResult(
                eval_run_id=run.id,
                eval_case_id=case.id,
                question_id=question.id,
                retrieval_run_id=retrieval_run.id,
                answer_id=answer.id,
                recall_at_20=recall,
                rerank_at_5=rerank,
                citation_support_rate=support,
                unsupported_claim_rate=1.0 - support,
                need_review=need_review,
                failure_category=failure_category,
                metrics_json={"evidence_sufficiency": answer.evidence_sufficiency.value},
            )
        )
        results.append(result)
    latencies = [store.retrieval_runs[result.retrieval_run_id].latency_ms for result in results]
    model_costs = [
        float(store.model_runs[store.answers[result.answer_id].model_run_id].cost_json.get("total_cost", 0.0))
        for result in results
        if store.answers[result.answer_id].model_run_id in store.model_runs
    ]
    sufficiency_values = [result.metrics_json.get("evidence_sufficiency") for result in results]
    failure_categories: dict[str, int] = {}
    for result in results:
        category = result.failure_category.value if result.failure_category else "none"
        failure_categories[category] = failure_categories.get(category, 0) + 1

    def percentile(values: list[int], percent: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        index = min(len(ordered) - 1, int(round((len(ordered) - 1) * percent)))
        return float(ordered[index])

    run.summary_metrics_json = {
        "case_count": len(results),
        "recall_at_20": mean([r.recall_at_20 for r in results]) if results else 0.0,
        "rerank_at_5": mean([r.rerank_at_5 for r in results]) if results else 0.0,
        "citation_support_rate": mean([r.citation_support_rate for r in results]) if results else 0.0,
        "unsupported_claim_rate": mean([r.unsupported_claim_rate for r in results]) if results else 0.0,
        "need_review_rate": mean([1.0 if r.need_review else 0.0 for r in results]) if results else 0.0,
        "evidence_sufficiency_rate": mean([1.0 if value == "sufficient" else 0.0 for value in sufficiency_values]) if results else 0.0,
        "failure_category_distribution": failure_categories,
        "latency_p50_ms": percentile(latencies, 0.50),
        "latency_p95_ms": percentile(latencies, 0.95),
        "model_cost": sum(model_costs),
    }
    store.add_eval_run(run)
    return run, results
