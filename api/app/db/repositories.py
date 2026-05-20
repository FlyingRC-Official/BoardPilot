from __future__ import annotations

from enum import Enum
from typing import Any, Iterable, TypeVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.orm import (
    AnswerOrm,
    AuditLogOrm,
    ChunkOrm,
    EvidenceOrm,
    IngestionJobOrm,
    ModelRunOrm,
    ProductAliasOrm,
    ProductOrm,
    QuestionAttachmentOrm,
    QuestionOrm,
    RetrievalCandidateOrm,
    RetrievalRunOrm,
    SourceArtifactOrm,
    SourceOrm,
    SourceVersionOrm,
)
from app.models.schemas import (
    Answer,
    AuditLog,
    Chunk,
    Evidence,
    IngestionJob,
    ModelRun,
    Product,
    ProductAlias,
    Question,
    QuestionAttachment,
    RetrievalCandidate,
    RetrievalRun,
    Source,
    SourceArtifact,
    SourceVersion,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


def _for_orm(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _for_orm(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_for_orm(item) for item in value]
    return value


def _model_to_orm_kwargs(model: BaseModel, orm_cls: type) -> dict[str, Any]:
    columns = orm_cls.__table__.columns.keys()
    return {key: _for_orm(value) for key, value in model.model_dump(mode="python").items() if key in columns}


def _orm_to_model(orm_obj: Any, model_cls: type[ModelT]) -> ModelT:
    data = {column.name: getattr(orm_obj, column.name) for column in orm_obj.__table__.columns}
    return model_cls(**data)


class CatalogRepository:
    """SQLAlchemy repository for the source catalog records that feed retrieval."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add_product(self, product: Product) -> Product:
        return self._merge(product, ProductOrm, Product)

    def list_products(self) -> list[Product]:
        return self._list(ProductOrm, Product)

    def add_alias(self, alias: ProductAlias) -> ProductAlias:
        return self._merge(alias, ProductAliasOrm, ProductAlias)

    def aliases_for_product(self, product_id: UUID) -> list[ProductAlias]:
        rows = self.session.scalars(select(ProductAliasOrm).where(ProductAliasOrm.product_id == str(product_id))).all()
        return [_orm_to_model(row, ProductAlias) for row in rows]

    def add_source(self, source: Source) -> Source:
        return self._merge(source, SourceOrm, Source)

    def list_sources(self) -> list[Source]:
        return self._list(SourceOrm, Source)

    def add_source_version(self, version: SourceVersion) -> SourceVersion:
        return self._merge(version, SourceVersionOrm, SourceVersion)

    def versions_for_source(self, source_id: UUID) -> list[SourceVersion]:
        rows = self.session.scalars(select(SourceVersionOrm).where(SourceVersionOrm.source_id == str(source_id))).all()
        return [_orm_to_model(row, SourceVersion) for row in rows]

    def add_artifact(self, artifact: SourceArtifact) -> SourceArtifact:
        return self._merge(artifact, SourceArtifactOrm, SourceArtifact)

    def artifacts_for_version(self, source_version_id: UUID) -> list[SourceArtifact]:
        rows = self.session.scalars(select(SourceArtifactOrm).where(SourceArtifactOrm.source_version_id == str(source_version_id))).all()
        return [_orm_to_model(row, SourceArtifact) for row in rows]

    def add_chunks(self, chunks: Iterable[Chunk]) -> list[Chunk]:
        return [self._merge(chunk, ChunkOrm, Chunk) for chunk in chunks]

    def chunks_for_version(self, source_version_id: UUID) -> list[Chunk]:
        rows = self.session.scalars(select(ChunkOrm).where(ChunkOrm.source_version_id == str(source_version_id))).all()
        return [_orm_to_model(row, Chunk) for row in rows]

    def _merge(self, model: ModelT, orm_cls: type, model_cls: type[ModelT]) -> ModelT:
        row = self.session.merge(orm_cls(**_model_to_orm_kwargs(model, orm_cls)))
        self.session.flush()
        return _orm_to_model(row, model_cls)

    def _list(self, orm_cls: type, model_cls: type[ModelT]) -> list[ModelT]:
        rows = self.session.scalars(select(orm_cls)).all()
        return [_orm_to_model(row, model_cls) for row in rows]


class RuntimeRepository:
    """SQLAlchemy repository for job and audit records shared by API and workers."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add_ingestion_job(self, job: IngestionJob) -> IngestionJob:
        return self._merge(job, IngestionJobOrm, IngestionJob)

    def get_ingestion_job(self, job_id: UUID) -> IngestionJob | None:
        row = self.session.get(IngestionJobOrm, str(job_id))
        return _orm_to_model(row, IngestionJob) if row else None

    def list_ingestion_jobs(self) -> list[IngestionJob]:
        rows = self.session.scalars(select(IngestionJobOrm)).all()
        return [_orm_to_model(row, IngestionJob) for row in rows]

    def add_audit_log(self, audit_log: AuditLog) -> AuditLog:
        return self._merge(audit_log, AuditLogOrm, AuditLog)

    def list_audit_logs(self) -> list[AuditLog]:
        rows = self.session.scalars(select(AuditLogOrm)).all()
        return [_orm_to_model(row, AuditLog) for row in rows]

    def _merge(self, model: ModelT, orm_cls: type, model_cls: type[ModelT]) -> ModelT:
        row = self.session.merge(orm_cls(**_model_to_orm_kwargs(model, orm_cls)))
        self.session.flush()
        return _orm_to_model(row, model_cls)


class RetrievalRepository:
    """SQLAlchemy repository for Ask, retrieval, evidence, and answer records."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add_question(self, question: Question) -> Question:
        return self._merge(question, QuestionOrm, Question)

    def add_question_attachment(self, attachment: QuestionAttachment) -> QuestionAttachment:
        return self._merge(attachment, QuestionAttachmentOrm, QuestionAttachment)

    def attachments_for_question(self, question_id: UUID) -> list[QuestionAttachment]:
        rows = self.session.scalars(select(QuestionAttachmentOrm).where(QuestionAttachmentOrm.question_id == str(question_id))).all()
        return [_orm_to_model(row, QuestionAttachment) for row in rows]

    def add_retrieval_run(self, run: RetrievalRun) -> RetrievalRun:
        return self._merge(run, RetrievalRunOrm, RetrievalRun)

    def add_candidates(self, candidates: Iterable[RetrievalCandidate]) -> list[RetrievalCandidate]:
        return [self._merge(candidate, RetrievalCandidateOrm, RetrievalCandidate) for candidate in candidates]

    def candidates_for_run(self, retrieval_run_id: UUID) -> list[RetrievalCandidate]:
        rows = self.session.scalars(select(RetrievalCandidateOrm).where(RetrievalCandidateOrm.retrieval_run_id == str(retrieval_run_id))).all()
        candidates = [_orm_to_model(row, RetrievalCandidate) for row in rows]
        return sorted(candidates, key=lambda candidate: (candidate.stage != "reranked", candidate.rank))

    def add_evidence(self, evidence: Iterable[Evidence]) -> list[Evidence]:
        return [self._merge(item, EvidenceOrm, Evidence) for item in evidence]

    def evidence_for_run(self, retrieval_run_id: UUID) -> list[Evidence]:
        rows = self.session.scalars(select(EvidenceOrm).where(EvidenceOrm.retrieval_run_id == str(retrieval_run_id))).all()
        return sorted([_orm_to_model(row, Evidence) for row in rows], key=lambda item: item.rank)

    def add_model_run(self, model_run: ModelRun) -> ModelRun:
        return self._merge(model_run, ModelRunOrm, ModelRun)

    def add_answer(self, answer: Answer) -> Answer:
        return self._merge(answer, AnswerOrm, Answer)

    def get_answer(self, answer_id: UUID) -> Answer | None:
        row = self.session.get(AnswerOrm, str(answer_id))
        return _orm_to_model(row, Answer) if row else None

    def _merge(self, model: ModelT, orm_cls: type, model_cls: type[ModelT]) -> ModelT:
        row = self.session.merge(orm_cls(**_model_to_orm_kwargs(model, orm_cls)))
        self.session.flush()
        return _orm_to_model(row, model_cls)
