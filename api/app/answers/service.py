import hashlib

from app.answers.citation import citation_map, verify_citations
from app.answers.sufficiency import assess_sufficiency
from app.db.store import InMemoryStore
from app.models.schemas import Answer, ModelRun, Question
from app.providers.llm import llm_provider


def estimate_model_cost(config_json: dict, input_words: int, output_words: int) -> dict:
    input_rate = float(config_json.get("input_cost_per_1k_words", 0.0) or 0.0)
    output_rate = float(config_json.get("output_cost_per_1k_words", 0.0) or 0.0)
    total = (input_words / 1000.0 * input_rate) + (output_words / 1000.0 * output_rate)
    return {
        "currency": config_json.get("currency", "USD"),
        "input_cost": input_words / 1000.0 * input_rate,
        "output_cost": output_words / 1000.0 * output_rate,
        "total_cost": total,
    }


def generate_answer(store: InMemoryStore, question: Question, retrieval_run_id, evidence: list) -> Answer:
    sufficiency, confidence = assess_sufficiency(evidence)
    evidence_quotes = [item.quote for item in evidence]
    llm_result = llm_provider.answer(question.raw_text, evidence_quotes)
    provider_config = store.active_provider_config("llm")
    provider_name = provider_config.provider_name if provider_config else llm_result.provider_name
    model_name = provider_config.model_name if provider_config else llm_result.model_name
    input_words = len(question.raw_text.split()) + sum(len(quote.split()) for quote in evidence_quotes)
    output_words = len(llm_result.answer_text.split())
    cost_json = estimate_model_cost(provider_config.config_json if provider_config else {}, input_words, output_words)
    model_run = store.add_model_run(
        ModelRun(
            provider_type="llm",
            provider_name=provider_name,
            model_name=model_name,
            input_hash=hashlib.sha256((question.raw_text + "\n\n".join(evidence_quotes)).encode("utf-8")).hexdigest(),
            prompt_version="mvp-v1",
            latency_ms=llm_result.latency_ms,
            token_usage_json={
                "input_words": input_words,
                "output_words": output_words,
            },
            cost_json=cost_json,
            status="failed" if llm_result.error_message else "completed",
            error_message=llm_result.error_message,
        )
    )
    citations = citation_map(evidence)
    answer = Answer(
        question_id=question.id,
        retrieval_run_id=retrieval_run_id,
        answer_text=llm_result.answer_text,
        citation_map_json=citations,
        evidence_sufficiency=sufficiency,
        confidence=confidence,
        provider_name=provider_name,
        model_name=model_name,
        model_run_id=model_run.id,
    )
    if not verify_citations(answer.citation_map_json, evidence):
        raise ValueError("answer cites evidence that was not saved")
    return store.add_answer(answer)
