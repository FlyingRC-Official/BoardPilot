from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def now() -> datetime:
    return datetime.utcnow()


class SourceType(str, Enum):
    pdf = "pdf"
    markdown = "markdown"
    webpage = "webpage"
    csv_faq = "csv_faq"
    ticket_export = "ticket_export"
    text_log = "text_log"
    image = "image"
    approved_faq = "approved_faq"
    manual_note = "manual_note"


class EvidenceSufficiency(str, Enum):
    sufficient = "sufficient"
    partial = "partial"
    insufficient = "insufficient"


class ReviewStatus(str, Enum):
    open = "open"
    in_review = "in_review"
    approved = "approved"
    rejected = "rejected"
    needs_source_update = "needs_source_update"
    converted_to_faq = "converted_to_faq"
    converted_to_eval_case = "converted_to_eval_case"


class FailureCategory(str, Enum):
    missing_source = "missing_source"
    stale_source = "stale_source"
    bad_parse = "bad_parse"
    bad_chunk = "bad_chunk"
    bad_query_normalization = "bad_query_normalization"
    bad_metadata_filter = "bad_metadata_filter"
    bad_keyword_recall = "bad_keyword_recall"
    bad_vector_recall = "bad_vector_recall"
    bad_merge_dedup = "bad_merge_dedup"
    bad_rerank = "bad_rerank"
    insufficient_evidence = "insufficient_evidence"
    unsupported_claim = "unsupported_claim"
    generation_error = "generation_error"
    product_alias_missing = "product_alias_missing"
    human_policy_required = "human_policy_required"


class ProductCreate(BaseModel):
    name: str
    slug: str
    description: str = ""
    status: str = "active"


class Product(ProductCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class ProductAliasCreate(BaseModel):
    alias: str
    alias_type: str = "user_facing"
    confidence: float = 1.0


class ProductAlias(ProductAliasCreate):
    id: UUID = Field(default_factory=uuid4)
    product_id: UUID
    created_at: datetime = Field(default_factory=now)


class SourceCreate(BaseModel):
    product_id: UUID
    title: str
    source_type: SourceType
    canonical_uri: str = ""
    status: str = "active"
    trust_level: str = "normal"


class Source(SourceCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class SourceVersionCreate(BaseModel):
    version_label: str = "v1"
    content: str
    parser_version: str = "mvp-text-v1"


class SourceVersion(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    source_id: UUID
    version_label: str
    content_hash: str
    status: str = "created"
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None
    parser_version: str = "mvp-text-v1"
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class SourceArtifact(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    source_version_id: UUID
    artifact_type: str = "original"
    storage_uri: str = ""
    mime_type: str = "text/plain"
    size_bytes: int = 0
    checksum: str = ""
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    content: str = ""
    created_at: datetime = Field(default_factory=now)


class Chunk(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    source_version_id: UUID
    product_id: UUID
    chunk_index: int
    title_path: str = ""
    content: str
    content_hash: str
    token_count: int
    char_start: int = 0
    char_end: int = 0
    page_number: Optional[int] = None
    section_name: str = ""
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    created_at: datetime = Field(default_factory=now)


class ChunkEmbedding(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    chunk_id: UUID
    provider_name: str
    model_name: str
    embedding_dimension: int
    vector: List[float]
    created_at: datetime = Field(default_factory=now)


class IngestionJobCreate(BaseModel):
    source_version_id: UUID


class IngestionJob(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    source_version_id: UUID
    status: str = "queued"
    error_message: str = ""
    chunk_count: int = 0
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class Question(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    product_id: Optional[UUID] = None
    raw_text: str
    normalized_text: str
    detected_entities_json: Dict[str, Any] = Field(default_factory=dict)
    metadata_filters_json: Dict[str, Any] = Field(default_factory=dict)
    user_id: str = "local"
    created_at: datetime = Field(default_factory=now)


class QuestionAttachmentCreate(BaseModel):
    artifact_id: UUID
    attachment_type: str = "file"
    description: str = ""


class QuestionAttachment(QuestionAttachmentCreate):
    id: UUID = Field(default_factory=uuid4)
    question_id: UUID
    created_at: datetime = Field(default_factory=now)


class RetrievalRun(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    question_id: UUID
    retrieval_config_json: Dict[str, Any] = Field(default_factory=dict)
    normalized_query: str
    filter_plan_json: Dict[str, Any] = Field(default_factory=dict)
    status: str = "completed"
    started_at: datetime = Field(default_factory=now)
    completed_at: datetime = Field(default_factory=now)
    latency_ms: int = 0
    error_message: str = ""


class RetrievalCandidate(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    retrieval_run_id: UUID
    chunk_id: UUID
    stage: str
    source: str
    keyword_score: float = 0.0
    vector_score: float = 0.0
    merged_score: float = 0.0
    rerank_score: float = 0.0
    rank: int = 0
    metadata_json: Dict[str, Any] = Field(default_factory=dict)


class Evidence(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    retrieval_run_id: UUID
    chunk_id: UUID
    rank: int
    score: float
    quote: str
    selection_reason: str
    created_at: datetime = Field(default_factory=now)


class Answer(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    question_id: UUID
    retrieval_run_id: UUID
    status: str = "candidate"
    answer_text: str
    citation_map_json: Dict[str, List[UUID]] = Field(default_factory=dict)
    evidence_sufficiency: EvidenceSufficiency
    confidence: float
    provider_name: str = "fake"
    model_name: str = "fake-citation-llm"
    prompt_version: str = "mvp-v1"
    model_run_id: Optional[UUID] = None
    created_at: datetime = Field(default_factory=now)


class ReviewItem(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    source_type: str
    question_id: Optional[UUID] = None
    answer_id: Optional[UUID] = None
    eval_result_id: Optional[UUID] = None
    status: ReviewStatus = ReviewStatus.open
    priority: int = 3
    failure_category: Optional[FailureCategory] = None
    reviewer_id: Optional[str] = None
    reviewer_notes: str = ""
    edited_answer_text: str = ""
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class ApprovedFAQ(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    product_id: UUID
    review_item_id: UUID
    question_text: str
    answer_text: str
    source_id: UUID
    status: str = "active"
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class ModelRun(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    provider_type: str
    provider_name: str
    model_name: str
    input_hash: str
    prompt_version: str = ""
    latency_ms: int = 0
    token_usage_json: Dict[str, Any] = Field(default_factory=dict)
    cost_json: Dict[str, Any] = Field(default_factory=dict)
    status: str = "completed"
    error_message: str = ""
    created_at: datetime = Field(default_factory=now)


class ProviderConfigCreate(BaseModel):
    provider_type: str
    provider_name: str
    model_name: str
    config_json: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class ProviderConfig(ProviderConfigCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=now)


class TicketCreate(BaseModel):
    product_id: Optional[UUID] = None
    external_id: str = ""
    title: str = ""
    body: str = ""
    status: str = "open"
    tags_json: List[str] = Field(default_factory=list)
    anonymized: bool = False


class Ticket(TicketCreate):
    id: UUID = Field(default_factory=uuid4)
    source_id: Optional[UUID] = None
    created_at: datetime = Field(default_factory=now)


class LogSourceCreate(BaseModel):
    product_id: Optional[UUID] = None
    log_type: str = ""
    content: str = ""
    device_context_json: Dict[str, Any] = Field(default_factory=dict)
    time_range_json: Dict[str, Any] = Field(default_factory=dict)


class LogSource(LogSourceCreate):
    id: UUID = Field(default_factory=uuid4)
    source_id: Optional[UUID] = None
    created_at: datetime = Field(default_factory=now)


class ImageAssetCreate(BaseModel):
    product_id: Optional[UUID] = None
    storage_uri: str
    image_type: str = ""
    manual_description: str = ""


class ImageAsset(ImageAssetCreate):
    id: UUID = Field(default_factory=uuid4)
    source_id: Optional[UUID] = None
    created_at: datetime = Field(default_factory=now)


class OcrResultCreate(BaseModel):
    ocr_text: str = ""
    confidence: float = 0.0


class OcrResult(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    image_asset_id: UUID
    provider_name: str
    model_name: str
    ocr_text: str = ""
    confidence: float = 0.0
    created_at: datetime = Field(default_factory=now)


class AuditLog(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: Optional[str] = None
    action: str
    entity_type: str
    entity_id: str
    before_json: Dict[str, Any] = Field(default_factory=dict)
    after_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=now)


class AskRequest(BaseModel):
    question: str
    product_id: Optional[UUID] = None
    metadata_filters_json: Dict[str, Any] = Field(default_factory=dict)
    attachments: List[QuestionAttachmentCreate] = Field(default_factory=list)


class AskResponse(BaseModel):
    question: Question
    retrieval_run: RetrievalRun
    candidates: List[RetrievalCandidate]
    evidence: List[Evidence]
    answer: Answer
    attachments: List[QuestionAttachment] = Field(default_factory=list)
    review_item: Optional[ReviewItem] = None


class EvalCaseCreate(BaseModel):
    product_id: Optional[UUID] = None
    question_text: str
    expected_source_ids_json: List[UUID] = Field(default_factory=list)
    expected_chunk_ids_json: List[UUID] = Field(default_factory=list)
    expected_answer_points_json: List[str] = Field(default_factory=list)
    tags_json: List[str] = Field(default_factory=list)
    difficulty: str = "normal"
    active: bool = True


class EvalCase(EvalCaseCreate):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class EvalRun(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    retrieval_config_json: Dict[str, Any] = Field(default_factory=dict)
    provider_config_json: Dict[str, Any] = Field(default_factory=dict)
    status: str = "completed"
    started_at: datetime = Field(default_factory=now)
    completed_at: datetime = Field(default_factory=now)
    summary_metrics_json: Dict[str, Any] = Field(default_factory=dict)


class EvalResult(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    eval_run_id: UUID
    eval_case_id: UUID
    question_id: UUID
    retrieval_run_id: UUID
    answer_id: UUID
    recall_at_20: float
    rerank_at_5: float
    citation_support_rate: float
    unsupported_claim_rate: float
    need_review: bool
    failure_category: Optional[FailureCategory] = None
    metrics_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=now)


class ReviewItemDetail(BaseModel):
    item: ReviewItem
    question: Optional[Question] = None
    attachments: List[QuestionAttachment] = Field(default_factory=list)
    answer: Optional[Answer] = None
    evidence: List[Evidence] = Field(default_factory=list)
    candidates: List[RetrievalCandidate] = Field(default_factory=list)
    eval_result: Optional[EvalResult] = None
