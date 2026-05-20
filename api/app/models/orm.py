from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.app_typing import JsonDict
from app.db.base import Base


def uuid_str() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.utcnow()


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class ProductOrm(Base, TimestampMixin):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)

    aliases: Mapped[list["ProductAliasOrm"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    sources: Mapped[list["SourceOrm"]] = relationship(back_populates="product")


class ProductAliasOrm(Base):
    __tablename__ = "product_aliases"
    __table_args__ = (UniqueConstraint("product_id", "alias", name="uq_product_alias"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    alias: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    alias_type: Mapped[str] = mapped_column(String(80), default="user_facing", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    product: Mapped[ProductOrm] = relationship(back_populates="aliases")


class SourceOrm(Base, TimestampMixin):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    canonical_uri: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    trust_level: Mapped[str] = mapped_column(String(50), default="normal", nullable=False)

    product: Mapped[ProductOrm] = relationship(back_populates="sources")
    versions: Mapped[list["SourceVersionOrm"]] = relationship(back_populates="source", cascade="all, delete-orphan")


class SourceVersionOrm(Base, TimestampMixin):
    __tablename__ = "source_versions"
    __table_args__ = (UniqueConstraint("source_id", "content_hash", name="uq_source_version_content"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), nullable=False, index=True)
    version_label: Mapped[str] = mapped_column(String(255), default="v1", nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), default="created", nullable=False)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    effective_from: Mapped[Optional[datetime]] = mapped_column(DateTime)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime)
    parser_version: Mapped[str] = mapped_column(String(120), default="mvp-text-v1", nullable=False)

    source: Mapped[SourceOrm] = relationship(back_populates="versions")
    artifacts: Mapped[list["SourceArtifactOrm"]] = relationship(back_populates="source_version", cascade="all, delete-orphan")
    chunks: Mapped[list["ChunkOrm"]] = relationship(back_populates="source_version", cascade="all, delete-orphan")


class SourceArtifactOrm(Base):
    __tablename__ = "source_artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    source_version_id: Mapped[str] = mapped_column(ForeignKey("source_versions.id"), nullable=False, index=True)
    artifact_type: Mapped[str] = mapped_column(String(80), nullable=False)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), default="text/plain", nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    checksum: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    metadata_json: Mapped[JsonDict] = mapped_column(JSON, default=dict, nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    source_version: Mapped[SourceVersionOrm] = relationship(back_populates="artifacts")


class ChunkOrm(Base):
    __tablename__ = "chunks"
    __table_args__ = (UniqueConstraint("source_version_id", "content_hash", name="uq_chunk_version_content"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    source_version_id: Mapped[str] = mapped_column(ForeignKey("source_versions.id"), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title_path: Mapped[str] = mapped_column(Text, default="", nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    char_start: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    page_number: Mapped[Optional[int]] = mapped_column(Integer)
    section_name: Mapped[str] = mapped_column(Text, default="", nullable=False)
    metadata_json: Mapped[JsonDict] = mapped_column(JSON, default=dict, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    source_version: Mapped[SourceVersionOrm] = relationship(back_populates="chunks")
    embeddings: Mapped[list["ChunkEmbeddingOrm"]] = relationship(back_populates="chunk", cascade="all, delete-orphan")


class ChunkEmbeddingOrm(Base):
    __tablename__ = "chunk_embeddings"
    __table_args__ = (UniqueConstraint("chunk_id", "provider_name", "model_name", name="uq_chunk_embedding_model"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    chunk_id: Mapped[str] = mapped_column(ForeignKey("chunks.id"), nullable=False, index=True)
    provider_name: Mapped[str] = mapped_column(String(120), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding_dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    vector: Mapped[list[float]] = mapped_column(Vector(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    chunk: Mapped[ChunkOrm] = relationship(back_populates="embeddings")


class QuestionOrm(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    product_id: Mapped[Optional[str]] = mapped_column(ForeignKey("products.id"), index=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    detected_entities_json: Mapped[JsonDict] = mapped_column(JSON, default=dict, nullable=False)
    metadata_filters_json: Mapped[JsonDict] = mapped_column(JSON, default=dict, nullable=False)
    user_id: Mapped[str] = mapped_column(String(255), default="local", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class QuestionAttachmentOrm(Base):
    __tablename__ = "question_attachments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), nullable=False, index=True)
    artifact_id: Mapped[str] = mapped_column(ForeignKey("source_artifacts.id"), nullable=False)
    attachment_type: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class RetrievalRunOrm(Base):
    __tablename__ = "retrieval_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), nullable=False, index=True)
    retrieval_config_json: Mapped[JsonDict] = mapped_column(JSON, default=dict, nullable=False)
    normalized_query: Mapped[str] = mapped_column(Text, nullable=False)
    filter_plan_json: Mapped[JsonDict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="completed", nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)


class RetrievalCandidateOrm(Base):
    __tablename__ = "retrieval_candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    retrieval_run_id: Mapped[str] = mapped_column(ForeignKey("retrieval_runs.id"), nullable=False, index=True)
    chunk_id: Mapped[str] = mapped_column(ForeignKey("chunks.id"), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    keyword_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    vector_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    merged_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rerank_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metadata_json: Mapped[JsonDict] = mapped_column(JSON, default=dict, nullable=False)


class EvidenceOrm(Base):
    __tablename__ = "evidences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    retrieval_run_id: Mapped[str] = mapped_column(ForeignKey("retrieval_runs.id"), nullable=False, index=True)
    chunk_id: Mapped[str] = mapped_column(ForeignKey("chunks.id"), nullable=False, index=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    selection_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class ModelRunOrm(Base):
    __tablename__ = "model_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    provider_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    provider_name: Mapped[str] = mapped_column(String(120), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    prompt_version: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    token_usage_json: Mapped[JsonDict] = mapped_column(JSON, default=dict, nullable=False)
    cost_json: Mapped[JsonDict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="completed", nullable=False)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class AnswerOrm(Base):
    __tablename__ = "answers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), nullable=False, index=True)
    retrieval_run_id: Mapped[str] = mapped_column(ForeignKey("retrieval_runs.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), default="candidate", nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    citation_map_json: Mapped[JsonDict] = mapped_column(JSON, default=dict, nullable=False)
    evidence_sufficiency: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    provider_name: Mapped[str] = mapped_column(String(120), default="fake", nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), default="fake-citation-llm", nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(120), default="mvp-v1", nullable=False)
    model_run_id: Mapped[Optional[str]] = mapped_column(ForeignKey("model_runs.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class EvalCaseOrm(Base, TimestampMixin):
    __tablename__ = "eval_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    product_id: Mapped[Optional[str]] = mapped_column(ForeignKey("products.id"), index=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    expected_source_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    expected_chunk_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    expected_answer_points_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    tags_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(50), default="normal", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)


class EvalRunOrm(Base):
    __tablename__ = "eval_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    retrieval_config_json: Mapped[JsonDict] = mapped_column(JSON, default=dict, nullable=False)
    provider_config_json: Mapped[JsonDict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="completed", nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    summary_metrics_json: Mapped[JsonDict] = mapped_column(JSON, default=dict, nullable=False)


class EvalResultOrm(Base):
    __tablename__ = "eval_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    eval_run_id: Mapped[str] = mapped_column(ForeignKey("eval_runs.id"), nullable=False, index=True)
    eval_case_id: Mapped[str] = mapped_column(ForeignKey("eval_cases.id"), nullable=False, index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), nullable=False)
    retrieval_run_id: Mapped[str] = mapped_column(ForeignKey("retrieval_runs.id"), nullable=False)
    answer_id: Mapped[str] = mapped_column(ForeignKey("answers.id"), nullable=False)
    recall_at_20: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rerank_at_5: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    citation_support_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    unsupported_claim_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    need_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failure_category: Mapped[Optional[str]] = mapped_column(String(120), index=True)
    metrics_json: Mapped[JsonDict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class ReviewItemOrm(Base, TimestampMixin):
    __tablename__ = "review_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    question_id: Mapped[Optional[str]] = mapped_column(ForeignKey("questions.id"), index=True)
    answer_id: Mapped[Optional[str]] = mapped_column(ForeignKey("answers.id"), index=True)
    eval_result_id: Mapped[Optional[str]] = mapped_column(ForeignKey("eval_results.id"), index=True)
    status: Mapped[str] = mapped_column(String(80), default="open", nullable=False, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    failure_category: Mapped[Optional[str]] = mapped_column(String(120), index=True)
    reviewer_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    reviewer_notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    edited_answer_text: Mapped[str] = mapped_column(Text, default="", nullable=False)


class ApprovedFAQOrm(Base, TimestampMixin):
    __tablename__ = "approved_faqs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    review_item_id: Mapped[str] = mapped_column(ForeignKey("review_items.id"), nullable=False, index=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[Optional[str]] = mapped_column(ForeignKey("sources.id"))
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)


class TicketOrm(Base):
    __tablename__ = "tickets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    product_id: Mapped[Optional[str]] = mapped_column(ForeignKey("products.id"), index=True)
    external_id: Mapped[str] = mapped_column(String(255), default="", nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, default="", nullable=False)
    body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(80), default="open", nullable=False)
    tags_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    anonymized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_id: Mapped[Optional[str]] = mapped_column(ForeignKey("sources.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class LogSourceOrm(Base):
    __tablename__ = "log_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    product_id: Mapped[Optional[str]] = mapped_column(ForeignKey("products.id"), index=True)
    source_id: Mapped[Optional[str]] = mapped_column(ForeignKey("sources.id"), index=True)
    log_type: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    device_context_json: Mapped[JsonDict] = mapped_column(JSON, default=dict, nullable=False)
    time_range_json: Mapped[JsonDict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class ImageAssetOrm(Base):
    __tablename__ = "image_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    product_id: Mapped[Optional[str]] = mapped_column(ForeignKey("products.id"), index=True)
    source_id: Mapped[Optional[str]] = mapped_column(ForeignKey("sources.id"), index=True)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    image_type: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    manual_description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class OcrResultOrm(Base):
    __tablename__ = "ocr_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    image_asset_id: Mapped[str] = mapped_column(ForeignKey("image_assets.id"), nullable=False, index=True)
    provider_name: Mapped[str] = mapped_column(String(120), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    ocr_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class ProviderConfigOrm(Base):
    __tablename__ = "provider_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    provider_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    provider_name: Mapped[str] = mapped_column(String(120), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    config_json: Mapped[JsonDict] = mapped_column(JSON, default=dict, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class AuditLogOrm(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    action: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    before_json: Mapped[JsonDict] = mapped_column(JSON, default=dict, nullable=False)
    after_json: Mapped[JsonDict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)


class IngestionJobOrm(Base, TimestampMixin):
    __tablename__ = "ingestion_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    source_version_id: Mapped[str] = mapped_column(ForeignKey("source_versions.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(80), default="queued", nullable=False, index=True)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
