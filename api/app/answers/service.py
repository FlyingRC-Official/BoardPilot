import hashlib
from typing import Optional

from app.answers.citation import citation_map, has_visible_citations, verify_citations
from app.answers.sufficiency import assess_sufficiency
from app.db.store import InMemoryStore
from app.models.schemas import Answer, EvidenceSufficiency, ModelRun, ProviderConfig, Question
from app.providers.base import LLMResult
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


def run_configured_llm(provider_config: Optional[ProviderConfig], question_text: str, evidence_quotes: list[str]) -> LLMResult:
    if provider_config and provider_config.provider_name != llm_provider.provider_name:
        return LLMResult(
            provider_config.provider_name,
            provider_config.model_name,
            0,
            error_message=f"LLM provider '{provider_config.provider_name}' is configured but no adapter is installed.",
            answer_text="Answer generation failed because the configured LLM provider is not available.",
        )
    return llm_provider.answer(question_text, evidence_quotes)


def generate_answer(store: InMemoryStore, question: Question, retrieval_run_id, evidence: list) -> Answer:
    sufficiency, confidence = assess_sufficiency(evidence)
    evidence_quotes = [item.quote for item in evidence]
    provider_config = store.active_provider_config("llm")
    provider_name = provider_config.provider_name if provider_config else llm_provider.provider_name
    model_name = provider_config.model_name if provider_config else llm_provider.model_name
    if sufficiency == EvidenceSufficiency.insufficient:
        answer_text = "I do not have enough saved evidence to answer this."
        model_run = store.add_model_run(
            ModelRun(
                provider_type="llm",
                provider_name=provider_name,
                model_name=model_name,
                input_hash=hashlib.sha256(question.raw_text.encode("utf-8")).hexdigest(),
                prompt_version="mvp-v1",
                token_usage_json={
                    "input_words": len(question.raw_text.split()),
                    "output_words": len(answer_text.split()),
                },
                cost_json=estimate_model_cost({}, len(question.raw_text.split()), len(answer_text.split())),
                status="skipped",
                error_message="insufficient evidence",
            )
        )
        return store.add_answer(
            Answer(
                question_id=question.id,
                retrieval_run_id=retrieval_run_id,
                status="insufficient_evidence",
                answer_text=answer_text,
                citation_map_json={},
                evidence_sufficiency=sufficiency,
                confidence=0.0,
                provider_name=provider_name,
                model_name=model_name,
                model_run_id=model_run.id,
            )
        )
    llm_result = run_configured_llm(provider_config, question.raw_text, evidence_quotes)
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
    citations = citation_map(evidence, llm_result.answer_text)
    generation_error = bool(llm_result.error_message)
    unsupported_claim_risk = bool(evidence and not citations and not generation_error)
    if unsupported_claim_risk:
        confidence = min(confidence, 0.2)
    status = "candidate"
    if sufficiency == EvidenceSufficiency.partial:
        status = "partial_evidence"
    if unsupported_claim_risk:
        status = "unsupported_claim_risk"
    if generation_error:
        status = "generation_error"
    answer = Answer(
        question_id=question.id,
        retrieval_run_id=retrieval_run_id,
        status=status,
        answer_text=llm_result.answer_text,
        citation_map_json=citations,
        evidence_sufficiency=sufficiency,
        confidence=0.0 if generation_error else confidence,
        provider_name=provider_name,
        model_name=model_name,
        model_run_id=model_run.id,
    )
    if not verify_citations(answer.citation_map_json, evidence) or not has_visible_citations(
        answer.answer_text,
        answer.citation_map_json,
    ):
        raise ValueError("answer cites invalid or invisible evidence")
    return store.add_answer(answer)
