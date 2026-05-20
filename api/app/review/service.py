from uuid import UUID

from app.db.store import InMemoryStore
from app.models.schemas import ApprovedFAQ, EvalCase, EvalCaseCreate, FailureCategory, ReviewItem, ReviewStatus, Source, SourceType, SourceVersionCreate
from app.sources.service import create_source_version


def approve_review_item(store: InMemoryStore, item_id: UUID, failure_category: FailureCategory, reviewer_id: str = "local") -> ReviewItem:
    item = store.review_items[item_id]
    item.failure_category = failure_category
    item.reviewer_id = reviewer_id
    item.status = ReviewStatus.approved
    store.audit_log.append({"action": "review_approved", "entity_type": "ReviewItem", "entity_id": str(item.id)})
    return item


def reject_review_item(store: InMemoryStore, item_id: UUID, failure_category: FailureCategory, reviewer_id: str = "local") -> ReviewItem:
    item = store.review_items[item_id]
    item.failure_category = failure_category
    item.reviewer_id = reviewer_id
    item.status = ReviewStatus.rejected
    store.audit_log.append({"action": "review_rejected", "entity_type": "ReviewItem", "entity_id": str(item.id)})
    return item


def review_to_eval_case(store: InMemoryStore, item_id: UUID) -> EvalCase:
    item = store.review_items[item_id]
    question = store.questions[item.question_id]
    case = store.add_eval_case(EvalCase(**EvalCaseCreate(product_id=question.product_id, question_text=question.raw_text).model_dump()))
    item.status = ReviewStatus.converted_to_eval_case
    store.audit_log.append({"action": "review_converted_to_eval_case", "entity_type": "ReviewItem", "entity_id": str(item.id)})
    return case


def review_to_faq(store: InMemoryStore, item_id: UUID) -> tuple[ApprovedFAQ, Source, list]:
    item = store.review_items[item_id]
    if item.question_id is None or item.answer_id is None:
        raise ValueError("review item must reference a question and answer")
    question = store.questions[item.question_id]
    answer = store.answers[item.answer_id]
    if question.product_id is None:
        raise ValueError("approved FAQ requires a product")

    answer_text = item.edited_answer_text.strip() or answer.answer_text
    source = store.add_source(
        Source(
            product_id=question.product_id,
            title=f"Approved FAQ: {question.raw_text[:80]}",
            source_type=SourceType.approved_faq,
            canonical_uri=f"boardpilot://review-items/{item.id}/faq",
            trust_level="approved",
        )
    )
    version, _artifact, chunks = create_source_version(
        store,
        source.id,
        SourceVersionCreate(
            version_label="approved",
            content=f"Question: {question.raw_text}\n\nAnswer: {answer_text}",
            parser_version="approved-faq-v1",
        ),
    )
    faq = store.add_approved_faq(
        ApprovedFAQ(
            product_id=question.product_id,
            review_item_id=item.id,
            question_text=question.raw_text,
            answer_text=answer_text,
            source_id=source.id,
        )
    )
    item.status = ReviewStatus.converted_to_faq
    store.audit_log.append(
        {
            "action": "review_converted_to_faq",
            "entity_type": "ReviewItem",
            "entity_id": str(item.id),
            "source_version_id": str(version.id),
        }
    )
    return faq, source, chunks
