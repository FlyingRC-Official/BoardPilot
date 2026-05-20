from app.models.schemas import Answer, EvidenceSufficiency, FailureCategory, ReviewItem


def route_answer_for_review(answer: Answer):
    if answer.status == "unsupported_claim_risk":
        return ReviewItem(
            source_type="low_confidence_answer",
            question_id=answer.question_id,
            answer_id=answer.id,
            priority=1,
            failure_category=FailureCategory.unsupported_claim,
        )
    if answer.evidence_sufficiency == EvidenceSufficiency.sufficient and answer.confidence >= 0.5:
        return None
    category = FailureCategory.insufficient_evidence
    source_type = "insufficient_evidence" if answer.evidence_sufficiency == EvidenceSufficiency.insufficient else "low_confidence_answer"
    return ReviewItem(
        source_type=source_type,
        question_id=answer.question_id,
        answer_id=answer.id,
        priority=1 if answer.evidence_sufficiency == EvidenceSufficiency.insufficient else 2,
        failure_category=category,
    )
