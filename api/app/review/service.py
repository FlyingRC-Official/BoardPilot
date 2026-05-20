from uuid import UUID

from app.db.store import InMemoryStore
from app.models.schemas import ApprovedFAQ, EvalCase, EvalCaseCreate, FailureCategory, ReviewItem, ReviewStatus, Source, SourceType, SourceVersionCreate
from app.sources.service import create_source_version


def approve_review_item(store: InMemoryStore, item_id: UUID, failure_category: FailureCategory, reviewer_id: str = "local") -> ReviewItem:
    item = store.review_items[item_id]
    item.failure_category = failure_category
    item.reviewer_id = reviewer_id
    item.status = ReviewStatus.approved
    store.add_audit_log(
        "review_approved",
        "ReviewItem",
        str(item.id),
        user_id=reviewer_id,
        after_json=item.model_dump(mode="json"),
    )
    return item


def reject_review_item(store: InMemoryStore, item_id: UUID, failure_category: FailureCategory, reviewer_id: str = "local") -> ReviewItem:
    item = store.review_items[item_id]
    item.failure_category = failure_category
    item.reviewer_id = reviewer_id
    item.status = ReviewStatus.rejected
    store.add_audit_log(
        "review_rejected",
        "ReviewItem",
        str(item.id),
        user_id=reviewer_id,
        after_json=item.model_dump(mode="json"),
    )
    return item


def mark_source_update_needed(
    store: InMemoryStore,
    item_id: UUID,
    failure_category: FailureCategory,
    reviewer_id: str = "local",
) -> ReviewItem:
    item = store.review_items[item_id]
    item.failure_category = failure_category
    item.reviewer_id = reviewer_id
    item.status = ReviewStatus.needs_source_update
    store.add_audit_log(
        "review_marked_source_update_needed",
        "ReviewItem",
        str(item.id),
        user_id=reviewer_id,
        after_json=item.model_dump(mode="json"),
    )
    return item


def review_to_eval_case(store: InMemoryStore, item_id: UUID) -> EvalCase:
    item = store.review_items[item_id]
    question = store.questions[item.question_id]
    answer = store.answers.get(item.answer_id) if item.answer_id else None
    evidence = store.evidence_for_run(answer.retrieval_run_id) if answer else []
    expected_chunk_ids = [evidence_item.chunk_id for evidence_item in evidence]
    expected_source_ids = []
    for evidence_item in evidence:
        chunk = store.chunks[evidence_item.chunk_id]
        source_version = store.source_versions[chunk.source_version_id]
        expected_source_ids.append(source_version.source_id)
    answer_point = item.edited_answer_text.strip() if item.edited_answer_text.strip() else (answer.answer_text if answer else "")
    case = store.add_eval_case(
        EvalCase(
            **EvalCaseCreate(
                product_id=question.product_id,
                question_text=question.raw_text,
                expected_source_ids_json=list(dict.fromkeys(expected_source_ids)),
                expected_chunk_ids_json=expected_chunk_ids,
                expected_answer_points_json=[answer_point] if answer_point else [],
                tags_json=["review_regression", item.source_type],
                difficulty="review",
            ).model_dump()
        )
    )
    item.status = ReviewStatus.converted_to_eval_case
    store.add_audit_log(
        "review_converted_to_eval_case",
        "ReviewItem",
        str(item.id),
        after_json={"eval_case_id": str(case.id)},
    )
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
    store.add_audit_log(
        "review_converted_to_faq",
        "ReviewItem",
        str(item.id),
        after_json={"approved_faq_id": str(faq.id), "source_id": str(source.id), "source_version_id": str(version.id)},
    )
    return faq, source, chunks
