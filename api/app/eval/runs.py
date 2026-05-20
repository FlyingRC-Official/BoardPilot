from statistics import mean

from app.answers.service import generate_answer
from app.db.store import InMemoryStore
from app.eval.metrics import citation_support_rate, recall_at_20, rerank_at_5
from app.models.schemas import EvalResult, EvalRun, EvidenceSufficiency, FailureCategory, Question
from app.retrieval.query_normalization import normalize_query
from app.retrieval.service import run_retrieval


def run_eval_batch(store: InMemoryStore, name: str = "MVP eval") -> tuple[EvalRun, list[EvalResult]]:
    run = EvalRun(name=name)
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
        need_review = answer.evidence_sufficiency != EvidenceSufficiency.sufficient or support < 1.0
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
                failure_category=FailureCategory.bad_rerank if rerank < 1.0 else None,
                metrics_json={"evidence_sufficiency": answer.evidence_sufficiency.value},
            )
        )
        results.append(result)
    run.summary_metrics_json = {
        "case_count": len(results),
        "recall_at_20": mean([r.recall_at_20 for r in results]) if results else 0.0,
        "rerank_at_5": mean([r.rerank_at_5 for r in results]) if results else 0.0,
        "citation_support_rate": mean([r.citation_support_rate for r in results]) if results else 0.0,
        "unsupported_claim_rate": mean([r.unsupported_claim_rate for r in results]) if results else 0.0,
        "need_review_rate": mean([1.0 if r.need_review else 0.0 for r in results]) if results else 0.0,
    }
    store.add_eval_run(run)
    return run, results
