from app.answers.citation import citation_map, verify_citations
from app.answers.sufficiency import assess_sufficiency
from app.db.store import InMemoryStore
from app.models.schemas import Answer, Question
from app.providers.llm import llm_provider


def generate_answer(store: InMemoryStore, question: Question, retrieval_run_id, evidence: list) -> Answer:
    sufficiency, confidence = assess_sufficiency(evidence)
    llm_result = llm_provider.answer(question.raw_text, [item.quote for item in evidence])
    citations = citation_map(evidence)
    answer = Answer(
        question_id=question.id,
        retrieval_run_id=retrieval_run_id,
        answer_text=llm_result.answer_text,
        citation_map_json=citations,
        evidence_sufficiency=sufficiency,
        confidence=confidence,
        provider_name=llm_result.provider_name,
        model_name=llm_result.model_name,
    )
    if not verify_citations(answer.citation_map_json, evidence):
        raise ValueError("answer cites evidence that was not saved")
    return store.add_answer(answer)

