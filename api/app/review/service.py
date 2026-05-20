from uuid import UUID

from app.db.store import InMemoryStore
from app.models.schemas import EvalCase, EvalCaseCreate, FailureCategory, ReviewItem, ReviewStatus


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

