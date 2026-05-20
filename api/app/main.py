import hashlib
from secrets import compare_digest
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.answers.service import generate_answer
from app.core.config import settings
from app.core.security import CurrentUser, get_current_user, require_roles
from app.db.repositories import CatalogRepository, RetrievalRepository, ReviewEvalRepository, RuntimeRepository
from app.db.session import get_session
from app.db.session import store
from app.eval.runs import run_eval_batch
from app.eval.seeds import seed_eval_cases
from app.ingestion.jobs import retry_ingestion_job as retry_ingestion_job_service
from app.ingestion.jobs import run_ingestion_job
from app.ingestion.queue import QUEUE_NAME, enqueue_ingestion_job
from app.models.schemas import (
    AskRequest,
    AskResponse,
    Answer,
    ApprovedFAQ,
    AuditLog,
    Chunk,
    ChunkEmbedding,
    EvalCase,
    EvalCaseCreate,
    EvalResult,
    EvalRun,
    Evidence,
    FailureCategory,
    ImageAsset,
    ImageAssetCreate,
    IngestionJob,
    IngestionJobCreate,
    LogSource,
    LogSourceCreate,
    ModelRun,
    OcrResult,
    OcrResultCreate,
    Product,
    ProductAlias,
    ProductAliasCreate,
    ProductCreate,
    ProviderConfig,
    ProviderConfigCreate,
    Question,
    QuestionAttachment,
    QuestionAttachmentCreate,
    RetrievalCandidate,
    RetrievalRun,
    ReviewItem,
    ReviewItemDetail,
    Source,
    SourceArtifact,
    SourceCreate,
    SourceType,
    SourceVersion,
    SourceVersionCreate,
    Ticket,
    TicketCreate,
    WebpageSnapshotCreate,
    now,
)
from app.products.service import create_alias, create_product, get_product, list_products
from app.retrieval.catalog import hydrate_retrieval_catalog
from app.retrieval.entity_extraction import detect_product_aliases
from app.retrieval.query_normalization import normalize_query, product_alias_expansions
from app.retrieval.service import run_retrieval
from app.review.routing import route_answer_for_review
from app.review.service import approve_review_item, mark_source_update_needed, reject_review_item, review_to_eval_case, review_to_faq
from app.providers.config_store import hydrate_provider_configs
from app.sources.service import (
    add_text_artifact_to_source_version,
    create_source,
    create_source_version,
    create_uploaded_source_version,
    create_webpage_snapshot_version,
    list_sources,
    safe_filename,
)
from app.providers.ocr import ocr_provider
from app.storage.local import LocalStorageProvider

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_ATTACHMENT_QUERY_CONTEXT_CHARS = 1200
API_KEY_EXEMPT_PATHS = {"/health"}


@app.middleware("http")
async def enforce_private_api_key(request: Request, call_next):
    if settings.api_key and request.method != "OPTIONS" and request.url.path not in API_KEY_EXEMPT_PATHS:
        supplied_key = request.headers.get("X-BoardPilot-API-Key", "")
        if not compare_digest(supplied_key, settings.api_key):
            return JSONResponse(status_code=401, content={"detail": "invalid API key"})
    return await call_next(request)


def not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="not found")


def save_runtime_job(session: Session, job: IngestionJob) -> None:
    try:
        RuntimeRepository(session).add_ingestion_job(job)
        session.commit()
    except SQLAlchemyError:
        session.rollback()


def list_runtime_jobs(session: Session) -> list[IngestionJob]:
    try:
        return RuntimeRepository(session).list_ingestion_jobs()
    except SQLAlchemyError:
        session.rollback()
        return []


def list_audit_logs_from_database(session: Session) -> list[AuditLog]:
    try:
        return RuntimeRepository(session).list_audit_logs()
    except SQLAlchemyError:
        session.rollback()
        return []


def get_runtime_job(session: Session, job_id: UUID) -> Optional[IngestionJob]:
    try:
        return RuntimeRepository(session).get_ingestion_job(job_id)
    except SQLAlchemyError:
        session.rollback()
        return None


def save_provider_config_to_database(session: Session, config: ProviderConfig) -> None:
    try:
        ReviewEvalRepository(session).add_provider_config(config)
        session.commit()
    except SQLAlchemyError:
        session.rollback()


def list_provider_configs_from_database(session: Session) -> list[ProviderConfig]:
    try:
        return ReviewEvalRepository(session).list_provider_configs()
    except SQLAlchemyError:
        session.rollback()
        return []


def get_provider_config_from_database(session: Session, config_id: UUID) -> Optional[ProviderConfig]:
    try:
        return ReviewEvalRepository(session).get_provider_config(config_id)
    except SQLAlchemyError:
        session.rollback()
        return None


def delete_provider_config_from_database(session: Session, config_id: UUID) -> Optional[ProviderConfig]:
    try:
        deleted = ReviewEvalRepository(session).delete_provider_config(config_id)
        session.commit()
        return deleted
    except SQLAlchemyError:
        session.rollback()
        return None


def save_product_to_database(session: Session, product: Product) -> None:
    try:
        CatalogRepository(session).add_product(product)
        session.commit()
    except SQLAlchemyError:
        session.rollback()


def list_products_from_database(session: Session) -> list[Product]:
    try:
        return CatalogRepository(session).list_products()
    except SQLAlchemyError:
        session.rollback()
        return []


def get_product_from_database(session: Session, product_id: UUID) -> Optional[Product]:
    try:
        return CatalogRepository(session).get_product(product_id)
    except SQLAlchemyError:
        session.rollback()
        return None


def save_alias_to_database(session: Session, alias: ProductAlias) -> None:
    try:
        CatalogRepository(session).add_alias(alias)
        session.commit()
    except SQLAlchemyError:
        session.rollback()


def list_aliases_from_database(session: Session, product_id: UUID) -> list[ProductAlias]:
    try:
        return CatalogRepository(session).aliases_for_product(product_id)
    except SQLAlchemyError:
        session.rollback()
        return []


def save_source_to_database(session: Session, source: Source) -> None:
    try:
        CatalogRepository(session).add_source(source)
        session.commit()
    except SQLAlchemyError:
        session.rollback()


def list_sources_from_database(session: Session) -> list[Source]:
    try:
        return CatalogRepository(session).list_sources()
    except SQLAlchemyError:
        session.rollback()
        return []


def get_source_from_database(session: Session, source_id: UUID) -> Optional[Source]:
    try:
        return CatalogRepository(session).get_source(source_id)
    except SQLAlchemyError:
        session.rollback()
        return None


def save_source_version_bundle_to_database(
    session: Session,
    version: SourceVersion,
    artifact: SourceArtifact,
    chunks: list[Chunk],
    chunk_embeddings: Optional[list[ChunkEmbedding]] = None,
) -> None:
    try:
        repo = CatalogRepository(session)
        repo.add_source_version(version)
        repo.add_artifact(artifact)
        repo.add_chunks(chunks)
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        return
    embeddings = chunk_embeddings if chunk_embeddings is not None else [embedding for chunk in chunks for embedding in store.embeddings_for_chunk(chunk.id)]
    if embeddings:
        save_chunk_embeddings_to_database(session, embeddings)


def save_source_version_to_database(session: Session, version: SourceVersion) -> None:
    try:
        CatalogRepository(session).add_source_version(version)
        session.commit()
    except SQLAlchemyError:
        session.rollback()


def save_chunks_to_database(session: Session, chunks: list[Chunk]) -> None:
    try:
        CatalogRepository(session).add_chunks(chunks)
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        return
    embeddings = [embedding for chunk in chunks for embedding in store.embeddings_for_chunk(chunk.id)]
    if embeddings:
        save_chunk_embeddings_to_database(session, embeddings)


def get_source_version_from_database(session: Session, version_id: UUID) -> Optional[SourceVersion]:
    try:
        return CatalogRepository(session).get_source_version(version_id)
    except SQLAlchemyError:
        session.rollback()
        return None


def list_source_versions_from_database(session: Session, source_id: UUID) -> list[SourceVersion]:
    try:
        return CatalogRepository(session).versions_for_source(source_id)
    except SQLAlchemyError:
        session.rollback()
        return []


def list_artifacts_from_database(session: Session, version_id: UUID) -> list[SourceArtifact]:
    try:
        return CatalogRepository(session).artifacts_for_version(version_id)
    except SQLAlchemyError:
        session.rollback()
        return []


def get_artifact_from_database(session: Session, artifact_id: UUID) -> Optional[SourceArtifact]:
    try:
        return CatalogRepository(session).get_artifact(artifact_id)
    except SQLAlchemyError:
        session.rollback()
        return None


def attachment_context_for_query(payload: QuestionAttachmentCreate, artifact: SourceArtifact) -> str:
    parts = [f"attached_{payload.attachment_type}"]
    if payload.description.strip():
        parts.append(payload.description.strip())
    if artifact.content.strip():
        parts.append(artifact.content.strip()[:MAX_ATTACHMENT_QUERY_CONTEXT_CHARS])
    return "\n".join(parts)


def list_chunks_from_database(session: Session, version_id: UUID) -> list[Chunk]:
    try:
        return CatalogRepository(session).chunks_for_version(version_id)
    except SQLAlchemyError:
        session.rollback()
        return []


def get_chunk_from_database(session: Session, chunk_id: UUID) -> Optional[Chunk]:
    try:
        return CatalogRepository(session).get_chunk(chunk_id)
    except SQLAlchemyError:
        session.rollback()
        return None


def save_chunk_embeddings_to_database(session: Session, embeddings: list[ChunkEmbedding]) -> None:
    try:
        CatalogRepository(session).add_chunk_embeddings(embeddings)
        session.commit()
    except SQLAlchemyError:
        session.rollback()


def list_chunk_embeddings_from_database(session: Session, chunk_id: UUID) -> list[ChunkEmbedding]:
    try:
        return CatalogRepository(session).embeddings_for_chunk(chunk_id)
    except SQLAlchemyError:
        session.rollback()
        return []


def hydrate_source_version_for_service(session: Session, source_version_id: UUID) -> Optional[SourceVersion]:
    version = store.source_versions.get(source_version_id) or get_source_version_from_database(session, source_version_id)
    if not version:
        return None
    store.source_versions[version.id] = version

    source = store.sources.get(version.source_id) or get_source_from_database(session, version.source_id)
    if source:
        store.sources[source.id] = source
        if source.product_id and source.product_id not in store.products:
            product = get_product_from_database(session, source.product_id)
            if product:
                store.products[product.id] = product

    for artifact in list_artifacts_from_database(session, version.id):
        store.source_artifacts[artifact.id] = artifact
    for chunk in list_chunks_from_database(session, version.id):
        store.chunks[chunk.id] = chunk
        store.chunk_hashes_by_version[chunk.source_version_id].add(chunk.content_hash)
    return version


def save_ask_response_to_database(
    session: Session,
    question: Question,
    retrieval_run: RetrievalRun,
    candidates: list[RetrievalCandidate],
    evidence: list[Evidence],
    answer: Answer,
    review_item: Optional[ReviewItem],
) -> None:
    try:
        retrieval_repo = RetrievalRepository(session)
        retrieval_repo.add_question(question)
        retrieval_repo.add_retrieval_run(retrieval_run)
        retrieval_repo.add_candidates(candidates)
        retrieval_repo.add_evidence(evidence)
        if answer.model_run_id and answer.model_run_id in store.model_runs:
            retrieval_repo.add_model_run(store.model_runs[answer.model_run_id])
        retrieval_repo.add_answer(answer)
        if review_item:
            ReviewEvalRepository(session).add_review_item(review_item)
        session.commit()
    except SQLAlchemyError:
        session.rollback()


def get_question_from_database(session: Session, question_id: UUID) -> Optional[Question]:
    try:
        return RetrievalRepository(session).get_question(question_id)
    except SQLAlchemyError:
        session.rollback()
        return None


def get_retrieval_run_from_database(session: Session, run_id: UUID) -> Optional[RetrievalRun]:
    try:
        return RetrievalRepository(session).get_retrieval_run(run_id)
    except SQLAlchemyError:
        session.rollback()
        return None


def list_retrieval_candidates_from_database(session: Session, run_id: UUID) -> list[RetrievalCandidate]:
    try:
        return RetrievalRepository(session).candidates_for_run(run_id)
    except SQLAlchemyError:
        session.rollback()
        return []


def get_answer_from_database(session: Session, answer_id: UUID) -> Optional[Answer]:
    try:
        return RetrievalRepository(session).get_answer(answer_id)
    except SQLAlchemyError:
        session.rollback()
        return None


def list_evidence_from_database(session: Session, run_id: UUID) -> list[Evidence]:
    try:
        return RetrievalRepository(session).evidence_for_run(run_id)
    except SQLAlchemyError:
        session.rollback()
        return []


def get_model_run_from_database(session: Session, model_run_id: UUID) -> Optional[ModelRun]:
    try:
        return RetrievalRepository(session).get_model_run(model_run_id)
    except SQLAlchemyError:
        session.rollback()
        return None


def save_question_attachment_to_database(session: Session, attachment: QuestionAttachment) -> None:
    try:
        RetrievalRepository(session).add_question_attachment(attachment)
        session.commit()
    except SQLAlchemyError:
        session.rollback()


def list_question_attachments_from_database(session: Session, question_id: UUID) -> list[QuestionAttachment]:
    try:
        return RetrievalRepository(session).attachments_for_question(question_id)
    except SQLAlchemyError:
        session.rollback()
        return []


def save_eval_case_to_database(session: Session, eval_case: EvalCase) -> None:
    try:
        ReviewEvalRepository(session).add_eval_case(eval_case)
        session.commit()
    except SQLAlchemyError:
        session.rollback()


def get_eval_case_from_database(session: Session, case_id: UUID) -> Optional[EvalCase]:
    try:
        return ReviewEvalRepository(session).get_eval_case(case_id)
    except SQLAlchemyError:
        session.rollback()
        return None


def list_eval_cases_from_database(session: Session) -> list[EvalCase]:
    try:
        return ReviewEvalRepository(session).list_eval_cases()
    except SQLAlchemyError:
        session.rollback()
        return []


def save_eval_run_results_to_database(session: Session, eval_run: EvalRun, results: list[EvalResult]) -> None:
    try:
        retrieval_repo = RetrievalRepository(session)
        review_repo = ReviewEvalRepository(session)
        review_repo.add_eval_run(eval_run)
        for result in results:
            question = store.questions.get(result.question_id)
            retrieval_run = store.retrieval_runs.get(result.retrieval_run_id)
            answer = store.answers.get(result.answer_id)
            if question and retrieval_run and answer:
                retrieval_repo.add_question(question)
                retrieval_repo.add_retrieval_run(retrieval_run)
                retrieval_repo.add_candidates(store.candidates_for_run(retrieval_run.id))
                retrieval_repo.add_evidence(store.evidence_for_run(retrieval_run.id))
                if answer.model_run_id and answer.model_run_id in store.model_runs:
                    retrieval_repo.add_model_run(store.model_runs[answer.model_run_id])
                retrieval_repo.add_answer(answer)
            review_repo.add_eval_result(result)
        session.commit()
    except SQLAlchemyError:
        session.rollback()


def get_eval_run_from_database(session: Session, run_id: UUID) -> Optional[EvalRun]:
    try:
        return ReviewEvalRepository(session).get_eval_run(run_id)
    except SQLAlchemyError:
        session.rollback()
        return None


def list_eval_runs_from_database(session: Session) -> list[EvalRun]:
    try:
        return ReviewEvalRepository(session).list_eval_runs()
    except SQLAlchemyError:
        session.rollback()
        return []


def get_eval_result_from_database(session: Session, result_id: UUID) -> Optional[EvalResult]:
    try:
        return ReviewEvalRepository(session).get_eval_result(result_id)
    except SQLAlchemyError:
        session.rollback()
        return None


def list_eval_results_from_database(session: Session, run_id: UUID) -> list[EvalResult]:
    try:
        return ReviewEvalRepository(session).results_for_eval_run(run_id)
    except SQLAlchemyError:
        session.rollback()
        return []


def save_review_item_to_database(session: Session, item: ReviewItem) -> None:
    try:
        ReviewEvalRepository(session).add_review_item(item)
        session.commit()
    except SQLAlchemyError:
        session.rollback()


def create_source_issue_review_item_for_failed_version(session: Session, version: SourceVersion) -> Optional[ReviewItem]:
    if version.status != "failed" or not version.error_message.strip():
        return None
    item = store.add_review_item(
        ReviewItem(
            source_type="source_issue",
            priority=1,
            failure_category=FailureCategory.bad_parse,
            reviewer_notes=f"SourceVersion {version.id} failed ingestion: {version.error_message}",
        )
    )
    save_review_item_to_database(session, item)
    return item


def review_item_from_answer_feedback(answer: Answer, payload: Dict[str, Any]) -> ReviewItem:
    feedback_type = payload.get("feedback_type", "user_feedback")
    source_type, failure_category, priority = {
        "missing_source": ("source_issue", FailureCategory.missing_source, 1),
        "incorrect": ("user_feedback", FailureCategory.unsupported_claim, 1),
        "needs_review": ("user_feedback", FailureCategory.human_policy_required, 2),
        "helpful": ("user_feedback", None, 4),
    }.get(feedback_type, ("user_feedback", None, 3))
    return ReviewItem(
        source_type=source_type,
        question_id=answer.question_id,
        answer_id=answer.id,
        priority=priority,
        failure_category=failure_category,
        reviewer_notes=payload.get("notes", ""),
    )


def get_review_item_from_database(session: Session, item_id: UUID) -> Optional[ReviewItem]:
    try:
        return ReviewEvalRepository(session).get_review_item(item_id)
    except SQLAlchemyError:
        session.rollback()
        return None


def list_review_items_from_database(session: Session) -> list[ReviewItem]:
    try:
        return ReviewEvalRepository(session).list_review_items()
    except SQLAlchemyError:
        session.rollback()
        return []


def hydrate_review_item_for_service(session: Session, item_id: UUID) -> Optional[ReviewItem]:
    item = store.review_items.get(item_id) or get_review_item_from_database(session, item_id)
    if item:
        store.review_items[item.id] = item
    return item


def hydrate_review_context_for_service(session: Session, item_id: UUID) -> Optional[ReviewItem]:
    item = hydrate_review_item_for_service(session, item_id)
    if not item:
        return None

    eval_result = get_eval_result_from_database(session, item.eval_result_id) if item.eval_result_id else None
    if eval_result:
        store.eval_results[eval_result.id] = eval_result

    answer_id = item.answer_id or (eval_result.answer_id if eval_result else None)
    answer = (store.answers.get(answer_id) or get_answer_from_database(session, answer_id)) if answer_id else None
    if answer:
        store.answers[answer.id] = answer

    question_id = item.question_id or (answer.question_id if answer else None) or (eval_result.question_id if eval_result else None)
    question = (store.questions.get(question_id) or get_question_from_database(session, question_id)) if question_id else None
    if question:
        store.questions[question.id] = question
        if question.product_id and question.product_id not in store.products:
            product = get_product_from_database(session, question.product_id)
            if product:
                store.products[product.id] = product

    retrieval_run_id = (answer.retrieval_run_id if answer else None) or (eval_result.retrieval_run_id if eval_result else None)
    retrieval_run = (store.retrieval_runs.get(retrieval_run_id) or get_retrieval_run_from_database(session, retrieval_run_id)) if retrieval_run_id else None
    if retrieval_run:
        store.retrieval_runs[retrieval_run.id] = retrieval_run
        for candidate in list_retrieval_candidates_from_database(session, retrieval_run.id):
            store.retrieval_candidates[candidate.id] = candidate
        for evidence in list_evidence_from_database(session, retrieval_run.id):
            store.evidences[evidence.id] = evidence
            chunk = store.chunks.get(evidence.chunk_id) or get_chunk_from_database(session, evidence.chunk_id)
            if not chunk:
                continue
            store.chunks[chunk.id] = chunk
            version = store.source_versions.get(chunk.source_version_id) or get_source_version_from_database(session, chunk.source_version_id)
            if not version:
                continue
            store.source_versions[version.id] = version
            source = store.sources.get(version.source_id) or get_source_from_database(session, version.source_id)
            if source:
                store.sources[source.id] = source
    return item


def save_approved_faq_to_database(session: Session, faq: ApprovedFAQ) -> None:
    try:
        ReviewEvalRepository(session).add_approved_faq(faq)
        session.commit()
    except SQLAlchemyError:
        session.rollback()


def get_approved_faq_from_database(session: Session, faq_id: UUID) -> Optional[ApprovedFAQ]:
    try:
        return ReviewEvalRepository(session).get_approved_faq(faq_id)
    except SQLAlchemyError:
        session.rollback()
        return None


def save_ticket_to_database(session: Session, ticket: Ticket) -> None:
    try:
        ReviewEvalRepository(session).add_ticket(ticket)
        session.commit()
    except SQLAlchemyError:
        session.rollback()


def list_tickets_from_database(session: Session) -> list[Ticket]:
    try:
        return ReviewEvalRepository(session).list_tickets()
    except SQLAlchemyError:
        session.rollback()
        return []


def save_log_source_to_database(session: Session, log_source: LogSource) -> None:
    try:
        ReviewEvalRepository(session).add_log_source(log_source)
        session.commit()
    except SQLAlchemyError:
        session.rollback()


def list_log_sources_from_database(session: Session) -> list[LogSource]:
    try:
        return ReviewEvalRepository(session).list_log_sources()
    except SQLAlchemyError:
        session.rollback()
        return []


def save_image_asset_to_database(session: Session, image_asset: ImageAsset) -> None:
    try:
        ReviewEvalRepository(session).add_image_asset(image_asset)
        session.commit()
    except SQLAlchemyError:
        session.rollback()


def get_image_asset_from_database(session: Session, image_asset_id: UUID) -> Optional[ImageAsset]:
    try:
        return ReviewEvalRepository(session).get_image_asset(image_asset_id)
    except SQLAlchemyError:
        session.rollback()
        return None


def list_image_assets_from_database(session: Session) -> list[ImageAsset]:
    try:
        return ReviewEvalRepository(session).list_image_assets()
    except SQLAlchemyError:
        session.rollback()
        return []


def save_ocr_result_to_database(session: Session, ocr_result: OcrResult) -> None:
    try:
        ReviewEvalRepository(session).add_ocr_result(ocr_result)
        session.commit()
    except SQLAlchemyError:
        session.rollback()


def list_ocr_results_from_database(session: Session, image_asset_id: UUID) -> list[OcrResult]:
    try:
        return ReviewEvalRepository(session).ocr_results_for_image(image_asset_id)
    except SQLAlchemyError:
        session.rollback()
        return []


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "boardpilot-api"}


@app.get("/version")
def version() -> dict:
    return {"version": "0.1.0", "environment": settings.environment}


@app.get("/providers")
def providers(session: Session = Depends(get_session)) -> dict:
    configs = hydrate_provider_configs(store, session)
    return {
        "llm": settings.llm_provider,
        "embedding": settings.embedding_provider,
        "reranker": settings.reranker_provider,
        "ocr": settings.ocr_provider,
        "configs": configs or list(store.provider_configs.values()),
    }


@app.get("/me", response_model=CurrentUser)
def me(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    return user


@app.post("/provider-configs", response_model=ProviderConfig)
def post_provider_config(
    payload: ProviderConfigCreate,
    user: CurrentUser = Depends(require_roles("admin")),
    session: Session = Depends(get_session),
) -> ProviderConfig:
    config = store.add_provider_config(ProviderConfig(**payload.model_dump()), user_id=user.user_id)
    save_provider_config_to_database(session, config)
    return config


@app.get("/provider-configs", response_model=list[ProviderConfig])
def get_provider_configs(
    _user: CurrentUser = Depends(require_roles("admin")),
    session: Session = Depends(get_session),
) -> list[ProviderConfig]:
    return hydrate_provider_configs(store, session) or list(store.provider_configs.values())


@app.patch("/provider-configs/{config_id}", response_model=ProviderConfig)
def patch_provider_config(
    config_id: UUID,
    payload: Dict[str, Any],
    user: CurrentUser = Depends(require_roles("admin")),
    session: Session = Depends(get_session),
) -> ProviderConfig:
    if config_id in store.provider_configs:
        config = store.provider_configs[config_id]
    else:
        config = get_provider_config_from_database(session, config_id)
    if not config:
        raise not_found()
    before_json = config.model_dump(mode="json")
    allowed_fields = {"provider_type", "provider_name", "model_name", "config_json", "enabled"}
    for key, value in payload.items():
        if key in allowed_fields:
            setattr(config, key, value)
    store.provider_configs[config_id] = config
    save_provider_config_to_database(session, config)
    store.add_audit_log(
        "provider_config_updated",
        "ProviderConfig",
        str(config.id),
        user_id=user.user_id,
        before_json=before_json,
        after_json=config.model_dump(mode="json"),
    )
    return config


@app.delete("/provider-configs/{config_id}")
def delete_provider_config(
    config_id: UUID,
    user: CurrentUser = Depends(require_roles("admin")),
    session: Session = Depends(get_session),
) -> dict:
    config = store.provider_configs.pop(config_id, None)
    database_config = delete_provider_config_from_database(session, config_id)
    config = config or database_config
    if not config:
        raise not_found()
    store.add_audit_log(
        "provider_config_deleted",
        "ProviderConfig",
        str(config.id),
        user_id=user.user_id,
        before_json=config.model_dump(mode="json"),
    )
    return {"status": "deleted"}


@app.post("/products", response_model=Product)
def post_product(
    payload: ProductCreate,
    _user: CurrentUser = Depends(require_roles("admin")),
    session: Session = Depends(get_session),
) -> Product:
    product = create_product(store, payload)
    save_product_to_database(session, product)
    return product


@app.get("/products", response_model=list[Product])
def get_products(session: Session = Depends(get_session)) -> list[Product]:
    return list_products_from_database(session) or list_products(store)


@app.get("/products/{product_id}", response_model=Product)
def get_product_endpoint(product_id: UUID, session: Session = Depends(get_session)) -> Product:
    database_product = get_product_from_database(session, product_id)
    if database_product:
        return database_product
    try:
        return get_product(store, product_id)
    except KeyError:
        raise not_found()


@app.patch("/products/{product_id}", response_model=Product)
def patch_product(
    product_id: UUID,
    payload: Dict[str, Any],
    _user: CurrentUser = Depends(require_roles("admin")),
    session: Session = Depends(get_session),
) -> Product:
    product = store.products.get(product_id) or get_product_from_database(session, product_id)
    if not product:
        raise not_found()
    for key, value in payload.items():
        if hasattr(product, key):
            setattr(product, key, value)
    product.updated_at = now()
    store.products[product_id] = product
    save_product_to_database(session, product)
    return product


@app.post("/products/{product_id}/aliases", response_model=ProductAlias)
def post_alias(
    product_id: UUID,
    payload: ProductAliasCreate,
    _user: CurrentUser = Depends(require_roles("admin", "support")),
    session: Session = Depends(get_session),
) -> ProductAlias:
    database_product = get_product_from_database(session, product_id)
    if database_product and product_id not in store.products:
        store.products[product_id] = database_product
    try:
        alias = create_alias(store, product_id, payload)
    except KeyError:
        raise not_found()
    save_alias_to_database(session, alias)
    return alias


@app.get("/products/{product_id}/aliases", response_model=list[ProductAlias])
def get_aliases(product_id: UUID, session: Session = Depends(get_session)) -> list[ProductAlias]:
    return list_aliases_from_database(session, product_id) or store.aliases_for_product(product_id)


@app.post("/sources", response_model=Source)
def post_source(
    payload: SourceCreate,
    _user: CurrentUser = Depends(require_roles("admin", "support")),
    session: Session = Depends(get_session),
) -> Source:
    database_product = get_product_from_database(session, payload.product_id)
    if database_product and payload.product_id not in store.products:
        store.products[payload.product_id] = database_product
    try:
        source = create_source(store, payload)
    except KeyError:
        raise not_found()
    save_source_to_database(session, source)
    return source


@app.get("/sources", response_model=list[Source])
def get_sources(session: Session = Depends(get_session)) -> list[Source]:
    return list_sources_from_database(session) or list_sources(store)


@app.get("/sources/{source_id}", response_model=Source)
def get_source(source_id: UUID, session: Session = Depends(get_session)) -> Source:
    database_source = get_source_from_database(session, source_id)
    if database_source:
        return database_source
    if source_id not in store.sources:
        raise not_found()
    return store.sources[source_id]


@app.patch("/sources/{source_id}", response_model=Source)
def patch_source(
    source_id: UUID,
    payload: Dict[str, Any],
    user: CurrentUser = Depends(require_roles("admin", "support")),
    session: Session = Depends(get_session),
) -> Source:
    source = store.sources.get(source_id) or get_source_from_database(session, source_id)
    if not source:
        raise not_found()
    before = source.model_dump(mode="json")
    for key, value in payload.items():
        if hasattr(source, key):
            setattr(source, key, value)
    source.updated_at = now()
    store.sources[source_id] = source
    save_source_to_database(session, source)
    store.add_audit_log(
        "source_updated",
        "Source",
        str(source.id),
        user_id=user.user_id,
        before_json=before,
        after_json=source.model_dump(mode="json"),
    )
    return source


@app.post("/sources/{source_id}/disable", response_model=Source)
def disable_source(
    source_id: UUID,
    payload: Dict[str, Any],
    user: CurrentUser = Depends(require_roles("admin", "support")),
    session: Session = Depends(get_session),
) -> Source:
    source = store.sources.get(source_id) or get_source_from_database(session, source_id)
    if not source:
        raise not_found()
    before = source.model_dump(mode="json")
    source.status = "disabled"
    source.updated_at = now()
    source_versions = [version for version in store.source_versions.values() if version.source_id == source_id]
    if not source_versions:
        source_versions = list_source_versions_from_database(session, source_id)
    disabled_chunks = []
    for version in source_versions:
        candidate_chunks = [chunk for chunk in store.chunks.values() if chunk.source_version_id == version.id]
        if not candidate_chunks:
            candidate_chunks = list_chunks_from_database(session, version.id)
        for chunk in candidate_chunks:
            chunk.enabled = False
            store.chunks[chunk.id] = chunk
            disabled_chunks.append(chunk)
    store.sources[source_id] = source
    save_source_to_database(session, source)
    save_chunks_to_database(session, disabled_chunks)
    store.add_audit_log(
        "source_disabled",
        "Source",
        str(source.id),
        user_id=user.user_id,
        before_json=before,
        after_json={**source.model_dump(mode="json"), "reason": payload.get("reason", ""), "disabled_chunk_count": len(disabled_chunks)},
    )
    return source


@app.post("/sources/{source_id}/versions")
def post_source_version(
    source_id: UUID,
    payload: SourceVersionCreate,
    _user: CurrentUser = Depends(require_roles("admin", "support")),
    session: Session = Depends(get_session),
) -> dict:
    hydrate_provider_configs(store, session)
    database_source = get_source_from_database(session, source_id)
    if database_source and source_id not in store.sources:
        store.sources[source_id] = database_source
    try:
        version, artifact, chunks = create_source_version(store, source_id, payload)
    except KeyError:
        raise not_found()
    save_source_version_bundle_to_database(session, version, artifact, chunks)
    review_item = create_source_issue_review_item_for_failed_version(session, version)
    return {"version": version, "artifact": artifact, "chunks": chunks, "review_item": review_item}


@app.post("/sources/{source_id}/versions/upload")
async def upload_source_version(
    source_id: UUID,
    version_label: str = Form("uploaded"),
    file: UploadFile = File(...),
    _user: CurrentUser = Depends(require_roles("admin", "support")),
    session: Session = Depends(get_session),
) -> dict:
    hydrate_provider_configs(store, session)
    database_source = get_source_from_database(session, source_id)
    if database_source and source_id not in store.sources:
        store.sources[source_id] = database_source
    try:
        content = await file.read()
        version, artifact, chunks = create_uploaded_source_version(
            store,
            source_id,
            version_label,
            file.filename or "artifact",
            file.content_type or "application/octet-stream",
            content,
        )
    except KeyError:
        raise not_found()
    save_source_version_bundle_to_database(session, version, artifact, chunks)
    review_item = create_source_issue_review_item_for_failed_version(session, version)
    return {"version": version, "artifact": artifact, "chunks": chunks, "review_item": review_item}


@app.post("/sources/{source_id}/versions/webpage")
def post_webpage_snapshot_version(
    source_id: UUID,
    payload: WebpageSnapshotCreate,
    _user: CurrentUser = Depends(require_roles("admin", "support")),
    session: Session = Depends(get_session),
) -> dict:
    hydrate_provider_configs(store, session)
    database_source = get_source_from_database(session, source_id)
    if database_source and source_id not in store.sources:
        store.sources[source_id] = database_source
    try:
        version, artifact, chunks = create_webpage_snapshot_version(store, source_id, payload)
    except KeyError:
        raise not_found()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    source = store.sources[source_id]
    if payload.url and not source.canonical_uri:
        source.canonical_uri = payload.url
        store.sources[source_id] = source
        save_source_to_database(session, source)
    save_source_version_bundle_to_database(session, version, artifact, chunks)
    review_item = create_source_issue_review_item_for_failed_version(session, version)
    return {"version": version, "artifact": artifact, "chunks": chunks, "review_item": review_item}


@app.get("/sources/{source_id}/versions")
def get_source_versions(source_id: UUID, session: Session = Depends(get_session)) -> list:
    database_versions = list_source_versions_from_database(session, source_id)
    return database_versions or [version for version in store.source_versions.values() if version.source_id == source_id]


@app.post("/source-versions/{version_id}/disable")
def disable_source_version(
    version_id: UUID,
    payload: Dict[str, Any],
    user: CurrentUser = Depends(require_roles("admin", "support")),
    session: Session = Depends(get_session),
) -> dict:
    version = store.source_versions.get(version_id) or get_source_version_from_database(session, version_id)
    if not version:
        raise not_found()
    before = version.model_dump(mode="json")
    version.status = "disabled"
    version.updated_at = now()
    disabled_chunks = []
    candidate_chunks = [chunk for chunk in store.chunks.values() if chunk.source_version_id == version_id]
    if not candidate_chunks:
        candidate_chunks = list_chunks_from_database(session, version_id)
    for chunk in candidate_chunks:
        chunk.enabled = False
        store.chunks[chunk.id] = chunk
        disabled_chunks.append(chunk)
    store.source_versions[version.id] = version
    save_source_version_to_database(session, version)
    save_chunks_to_database(session, disabled_chunks)
    store.add_audit_log(
        "source_version_disabled",
        "SourceVersion",
        str(version.id),
        user_id=user.user_id,
        before_json=before,
        after_json={**version.model_dump(mode="json"), "reason": payload.get("reason", ""), "disabled_chunk_count": len(disabled_chunks)},
    )
    return {"version": version, "disabled_chunk_count": len(disabled_chunks)}


@app.post("/sources/{source_id}/versions/{version_id}/artifacts")
def post_source_artifact(
    source_id: UUID,
    version_id: UUID,
    payload: SourceVersionCreate,
    _user: CurrentUser = Depends(require_roles("admin", "support")),
    session: Session = Depends(get_session),
) -> dict:
    hydrate_provider_configs(store, session)
    if version_id not in store.source_versions:
        hydrate_source_version_for_service(session, version_id)
    elif source_id not in store.sources:
        database_source = get_source_from_database(session, source_id)
        if database_source:
            store.sources[source_id] = database_source
    if source_id not in store.sources or version_id not in store.source_versions:
        raise not_found()
    try:
        version, artifact, chunks = add_text_artifact_to_source_version(store, source_id, version_id, payload)
    except KeyError:
        raise not_found() from None
    save_source_version_bundle_to_database(session, version, artifact, chunks)
    review_item = create_source_issue_review_item_for_failed_version(session, version)
    return {"version": version, "artifact": artifact, "chunks": chunks, "review_item": review_item}


@app.get("/source-versions/{version_id}/chunks")
def get_chunks(version_id: UUID, session: Session = Depends(get_session)) -> list:
    database_chunks = list_chunks_from_database(session, version_id)
    return database_chunks or [chunk for chunk in store.chunks.values() if chunk.source_version_id == version_id]


@app.get("/source-versions/{version_id}/artifacts")
def get_source_version_artifacts(version_id: UUID, session: Session = Depends(get_session)) -> list:
    database_artifacts = list_artifacts_from_database(session, version_id)
    if database_artifacts:
        return database_artifacts
    if version_id not in store.source_versions:
        raise not_found()
    return [artifact for artifact in store.source_artifacts.values() if artifact.source_version_id == version_id]


@app.get("/chunks/{chunk_id}/embeddings")
def get_chunk_embeddings(chunk_id: UUID, session: Session = Depends(get_session)) -> list:
    database_embeddings = list_chunk_embeddings_from_database(session, chunk_id)
    if database_embeddings:
        return database_embeddings
    database_chunk = get_chunk_from_database(session, chunk_id)
    if database_chunk:
        store.chunks[database_chunk.id] = database_chunk
    if chunk_id not in store.chunks:
        raise not_found()
    return store.embeddings_for_chunk(chunk_id)


@app.post("/ingestion/jobs")
def post_ingestion_job(
    payload: IngestionJobCreate,
    _user: CurrentUser = Depends(require_roles("admin", "support")),
    session: Session = Depends(get_session),
) -> dict:
    if not hydrate_source_version_for_service(session, payload.source_version_id):
        raise not_found()
    hydrate_provider_configs(store, session)
    job, chunks = run_ingestion_job(payload.source_version_id)
    save_runtime_job(session, job)
    save_source_version_to_database(session, store.source_versions[payload.source_version_id])
    save_chunks_to_database(session, chunks)
    review_item = create_source_issue_review_item_for_failed_version(session, store.source_versions[payload.source_version_id])
    return {"job": job, "chunks": chunks, "review_item": review_item}


@app.post("/ingestion/jobs/enqueue")
def enqueue_ingestion_job_endpoint(
    payload: IngestionJobCreate,
    _user: CurrentUser = Depends(require_roles("admin", "support")),
    session: Session = Depends(get_session),
) -> dict:
    if not hydrate_source_version_for_service(session, payload.source_version_id):
        raise not_found()
    job = store.add_ingestion_job(IngestionJob(source_version_id=payload.source_version_id))
    save_runtime_job(session, job)
    try:
        enqueue_ingestion_job(job)
    except Exception as exc:
        job.status = "failed"
        job.error_message = f"queue enqueue failed: {exc}"
        job.updated_at = now()
        save_runtime_job(session, job)
        raise HTTPException(status_code=503, detail="failed to enqueue ingestion job")
    return {"job": job, "queue": QUEUE_NAME}


@app.get("/ingestion/jobs")
def get_ingestion_jobs(session: Session = Depends(get_session)) -> list[IngestionJob]:
    database_jobs = list_runtime_jobs(session)
    return database_jobs or list(store.ingestion_jobs.values())


@app.get("/ingestion/jobs/{job_id}")
def get_ingestion_job(job_id: UUID, session: Session = Depends(get_session)) -> IngestionJob:
    database_job = get_runtime_job(session, job_id)
    if database_job:
        return database_job
    if job_id not in store.ingestion_jobs:
        raise not_found()
    return store.ingestion_jobs[job_id]


@app.post("/ingestion/jobs/{job_id}/retry")
def retry_ingestion_job(
    job_id: UUID,
    _user: CurrentUser = Depends(require_roles("admin", "support")),
    session: Session = Depends(get_session),
) -> dict:
    job = store.ingestion_jobs.get(job_id) or get_runtime_job(session, job_id)
    if not job:
        raise not_found()
    store.ingestion_jobs[job.id] = job
    if not hydrate_source_version_for_service(session, job.source_version_id):
        raise not_found()
    hydrate_provider_configs(store, session)
    job, chunks = retry_ingestion_job_service(job_id)
    save_runtime_job(session, job)
    save_source_version_to_database(session, store.source_versions[job.source_version_id])
    save_chunks_to_database(session, chunks)
    return {"job": job, "chunks": chunks}


@app.post("/ask", response_model=AskResponse)
def ask(
    payload: AskRequest,
    user: CurrentUser = Depends(require_roles("admin", "support", "reviewer")),
    session: Session = Depends(get_session),
) -> AskResponse:
    hydrate_provider_configs(store, session)
    hydrate_retrieval_catalog(store, session, payload.product_id)
    validated_attachments: list[tuple[QuestionAttachmentCreate, SourceArtifact]] = []
    attachment_contexts: list[str] = []
    for attachment_payload in payload.attachments:
        artifact = store.source_artifacts.get(attachment_payload.artifact_id) or get_artifact_from_database(
            session, attachment_payload.artifact_id
        )
        if not artifact:
            raise not_found()
        store.source_artifacts[artifact.id] = artifact
        validated_attachments.append((attachment_payload, artifact))
        context = attachment_context_for_query(attachment_payload, artifact)
        if context.strip():
            attachment_contexts.append(context)
    retrieval_text = "\n\n".join([payload.question, *attachment_contexts])
    detected_entities = detect_product_aliases(store, retrieval_text)
    normalized_query = normalize_query(retrieval_text, product_alias_expansions(detected_entities))
    question = store.add_question(
        Question(
            product_id=payload.product_id,
            raw_text=payload.question,
            normalized_text=normalized_query,
            detected_entities_json=detected_entities,
            metadata_filters_json=payload.metadata_filters_json,
            user_id=user.user_id,
        )
    )
    attachments: list[QuestionAttachment] = []
    for attachment_payload, _artifact in validated_attachments:
        attachment = store.add_question_attachment(QuestionAttachment(**attachment_payload.model_dump(), question_id=question.id))
        save_question_attachment_to_database(session, attachment)
        attachments.append(attachment)
    retrieval_run, candidates, evidence = run_retrieval(store, question)
    answer = generate_answer(store, question, retrieval_run.id, evidence)
    review_item = route_answer_for_review(answer)
    if retrieval_run.error_message:
        review_item = ReviewItem(
            source_type="retrieval_issue",
            question_id=question.id,
            answer_id=answer.id,
            priority=1,
            failure_category=FailureCategory.bad_rerank,
            reviewer_notes=retrieval_run.error_message,
        )
    if review_item:
        review_item = store.add_review_item(review_item)
    save_ask_response_to_database(session, question, retrieval_run, candidates, evidence, answer, review_item)
    return AskResponse(
        question=question,
        retrieval_run=retrieval_run,
        candidates=candidates,
        evidence=evidence,
        answer=answer,
        attachments=attachments,
        review_item=review_item,
    )


@app.get("/questions/{question_id}")
def get_question(question_id: UUID, session: Session = Depends(get_session)) -> Question:
    database_question = get_question_from_database(session, question_id)
    if database_question:
        return database_question
    if question_id not in store.questions:
        raise not_found()
    return store.questions[question_id]


@app.post("/questions/{question_id}/attachments", response_model=QuestionAttachment)
def post_question_attachment(
    question_id: UUID,
    payload: QuestionAttachmentCreate,
    _user: CurrentUser = Depends(require_roles("admin", "support", "reviewer")),
    session: Session = Depends(get_session),
) -> QuestionAttachment:
    database_question = get_question_from_database(session, question_id)
    database_artifact = get_artifact_from_database(session, payload.artifact_id)
    if database_question and question_id not in store.questions:
        store.questions[question_id] = database_question
    if question_id not in store.questions or (payload.artifact_id not in store.source_artifacts and not database_artifact):
        raise not_found()
    attachment = store.add_question_attachment(QuestionAttachment(**payload.model_dump(), question_id=question_id))
    save_question_attachment_to_database(session, attachment)
    return attachment


@app.get("/questions/{question_id}/attachments", response_model=list[QuestionAttachment])
def get_question_attachments(question_id: UUID, session: Session = Depends(get_session)) -> list[QuestionAttachment]:
    database_attachments = list_question_attachments_from_database(session, question_id)
    if database_attachments:
        return database_attachments
    if question_id not in store.questions:
        raise not_found()
    return store.attachments_for_question(question_id)


@app.get("/retrieval-runs/{run_id}")
def get_retrieval_run(run_id: UUID, session: Session = Depends(get_session)):
    database_run = get_retrieval_run_from_database(session, run_id)
    if database_run:
        return database_run
    if run_id not in store.retrieval_runs:
        raise not_found()
    return store.retrieval_runs[run_id]


@app.get("/retrieval-runs/{run_id}/candidates")
def get_retrieval_candidates(run_id: UUID, session: Session = Depends(get_session)) -> list:
    return list_retrieval_candidates_from_database(session, run_id) or store.candidates_for_run(run_id)


@app.get("/answers/{answer_id}")
def get_answer(answer_id: UUID, session: Session = Depends(get_session)):
    database_answer = get_answer_from_database(session, answer_id)
    if database_answer:
        return database_answer
    if answer_id not in store.answers:
        raise not_found()
    return store.answers[answer_id]


@app.get("/answers/{answer_id}/evidence")
def get_answer_evidence(answer_id: UUID, session: Session = Depends(get_session)) -> list:
    answer = store.answers.get(answer_id) or get_answer_from_database(session, answer_id)
    if not answer:
        raise not_found()
    return list_evidence_from_database(session, answer.retrieval_run_id) or store.evidence_for_run(answer.retrieval_run_id)


@app.get("/model-runs/{model_run_id}")
def get_model_run(model_run_id: UUID, session: Session = Depends(get_session)):
    database_model_run = get_model_run_from_database(session, model_run_id)
    if database_model_run:
        return database_model_run
    if model_run_id not in store.model_runs:
        raise not_found()
    return store.model_runs[model_run_id]


@app.post("/answers/{answer_id}/feedback")
def post_feedback(
    answer_id: UUID,
    payload: Dict[str, Any],
    _user: CurrentUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ReviewItem:
    answer = store.answers.get(answer_id) or get_answer_from_database(session, answer_id)
    if not answer:
        raise not_found()
    item = review_item_from_answer_feedback(answer, payload)
    item = store.add_review_item(item)
    save_review_item_to_database(session, item)
    return item


@app.post("/eval-cases", response_model=EvalCase)
def post_eval_case(
    payload: EvalCaseCreate,
    _user: CurrentUser = Depends(require_roles("admin", "support", "reviewer")),
    session: Session = Depends(get_session),
) -> EvalCase:
    case = store.add_eval_case(EvalCase(**payload.model_dump()))
    save_eval_case_to_database(session, case)
    return case


@app.get("/eval-cases", response_model=list[EvalCase])
def get_eval_cases(session: Session = Depends(get_session)) -> list[EvalCase]:
    return list_eval_cases_from_database(session) or list(store.eval_cases.values())


@app.post("/eval-cases/seed")
def post_seed_eval_cases(
    _user: CurrentUser = Depends(require_roles("admin", "support", "reviewer")),
    session: Session = Depends(get_session),
) -> dict:
    product, source, cases = seed_eval_cases(store)
    save_product_to_database(session, product)
    save_source_to_database(session, source)
    for case in cases:
        save_eval_case_to_database(session, case)
    return {"product": product, "source": source, "cases": cases, "case_count": len(cases)}


@app.get("/eval-cases/{case_id}", response_model=EvalCase)
def get_eval_case(case_id: UUID, session: Session = Depends(get_session)) -> EvalCase:
    database_case = get_eval_case_from_database(session, case_id)
    if database_case:
        return database_case
    if case_id not in store.eval_cases:
        raise not_found()
    return store.eval_cases[case_id]


@app.patch("/eval-cases/{case_id}", response_model=EvalCase)
def patch_eval_case(
    case_id: UUID,
    payload: Dict[str, Any],
    user: CurrentUser = Depends(require_roles("admin", "support", "reviewer")),
    session: Session = Depends(get_session),
) -> EvalCase:
    case = store.eval_cases.get(case_id) or get_eval_case_from_database(session, case_id)
    if not case:
        raise not_found()
    before = case.model_dump(mode="json")
    for key, value in payload.items():
        if key in {"expected_source_ids_json", "expected_chunk_ids_json"}:
            value = [UUID(str(item)) for item in value]
        if hasattr(case, key):
            setattr(case, key, value)
    case.updated_at = now()
    store.eval_cases[case.id] = case
    save_eval_case_to_database(session, case)
    store.add_audit_log(
        "eval_case_modified",
        "EvalCase",
        str(case.id),
        user_id=user.user_id,
        before_json=before,
        after_json=case.model_dump(mode="json"),
    )
    return case


@app.post("/eval-runs")
def post_eval_run(
    payload: Optional[Dict[str, Any]] = None,
    _user: CurrentUser = Depends(require_roles("admin", "support", "reviewer")),
    session: Session = Depends(get_session),
) -> dict:
    hydrate_provider_configs(store, session)
    hydrate_retrieval_catalog(store, session)
    for case in list_eval_cases_from_database(session):
        store.eval_cases.setdefault(case.id, case)
    run, results = run_eval_batch(store, (payload or {}).get("name", "MVP eval"))
    save_eval_run_results_to_database(session, run, results)
    return {"eval_run": run, "results": results}


@app.get("/eval-runs")
def get_eval_runs(session: Session = Depends(get_session)) -> list:
    return list_eval_runs_from_database(session) or list(store.eval_runs.values())


@app.get("/eval-runs/compare")
def compare_eval_runs(run_a: UUID, run_b: UUID, session: Session = Depends(get_session)) -> dict:
    baseline = store.eval_runs.get(run_a) or get_eval_run_from_database(session, run_a)
    candidate = store.eval_runs.get(run_b) or get_eval_run_from_database(session, run_b)
    if not baseline or not candidate:
        raise not_found()
    deltas = {}
    for key, candidate_value in candidate.summary_metrics_json.items():
        baseline_value = baseline.summary_metrics_json.get(key)
        if isinstance(candidate_value, (int, float)) and isinstance(baseline_value, (int, float)):
            deltas[key] = candidate_value - baseline_value
    return {"baseline": baseline, "candidate": candidate, "deltas": deltas}


@app.get("/eval-runs/{run_id}")
def get_eval_run(run_id: UUID, session: Session = Depends(get_session)):
    database_run = get_eval_run_from_database(session, run_id)
    if database_run:
        return database_run
    if run_id not in store.eval_runs:
        raise not_found()
    return store.eval_runs[run_id]


@app.get("/eval-runs/{run_id}/results")
def get_eval_results(run_id: UUID, session: Session = Depends(get_session)) -> list:
    return list_eval_results_from_database(session, run_id) or [result for result in store.eval_results.values() if result.eval_run_id == run_id]


@app.post("/eval-results/{result_id}/to-review")
def eval_result_to_review(
    result_id: UUID,
    _user: CurrentUser = Depends(require_roles("admin", "support", "reviewer")),
    session: Session = Depends(get_session),
) -> ReviewItem:
    result = store.eval_results.get(result_id) or get_eval_result_from_database(session, result_id)
    if not result:
        raise not_found()
    item = store.add_review_item(
        ReviewItem(
            source_type="eval_failure",
            question_id=result.question_id,
            answer_id=result.answer_id,
            eval_result_id=result.id,
            failure_category=result.failure_category,
        )
    )
    save_review_item_to_database(session, item)
    return item


@app.get("/review-items", response_model=list[ReviewItem])
def get_review_items(session: Session = Depends(get_session)) -> list[ReviewItem]:
    return list_review_items_from_database(session) or list(store.review_items.values())


@app.get("/review-items/{item_id}", response_model=ReviewItem)
def get_review_item(item_id: UUID, session: Session = Depends(get_session)) -> ReviewItem:
    database_item = get_review_item_from_database(session, item_id)
    if database_item:
        return database_item
    if item_id not in store.review_items:
        raise not_found()
    return store.review_items[item_id]


@app.get("/review-items/{item_id}/detail", response_model=ReviewItemDetail)
def get_review_item_detail(item_id: UUID, session: Session = Depends(get_session)) -> ReviewItemDetail:
    item = store.review_items.get(item_id) or get_review_item_from_database(session, item_id)
    if not item:
        raise not_found()
    eval_result = store.eval_results.get(item.eval_result_id) if item.eval_result_id else None
    answer_id = item.answer_id or (eval_result.answer_id if eval_result else None)
    answer = (store.answers.get(answer_id) or get_answer_from_database(session, answer_id)) if answer_id else None
    question_id = item.question_id or (answer.question_id if answer else None) or (eval_result.question_id if eval_result else None)
    question = (store.questions.get(question_id) or get_question_from_database(session, question_id)) if question_id else None
    retrieval_run_id = (answer.retrieval_run_id if answer else None) or (eval_result.retrieval_run_id if eval_result else None)
    evidence = (list_evidence_from_database(session, retrieval_run_id) or store.evidence_for_run(retrieval_run_id)) if retrieval_run_id else []
    candidates = (list_retrieval_candidates_from_database(session, retrieval_run_id) or store.candidates_for_run(retrieval_run_id)) if retrieval_run_id else []
    attachments = (list_question_attachments_from_database(session, question_id) or store.attachments_for_question(question_id)) if question_id else []
    return ReviewItemDetail(
        item=item,
        question=question,
        attachments=attachments,
        answer=answer,
        evidence=evidence,
        candidates=candidates,
        eval_result=eval_result,
    )


@app.get("/audit-logs", response_model=list[AuditLog])
def get_audit_logs(
    _user: CurrentUser = Depends(require_roles("admin")),
    session: Session = Depends(get_session),
) -> list[AuditLog]:
    return list_audit_logs_from_database(session) or list(store.audit_logs.values())


@app.patch("/review-items/{item_id}", response_model=ReviewItem)
def patch_review_item(
    item_id: UUID,
    payload: Dict[str, Any],
    user: CurrentUser = Depends(require_roles("admin", "reviewer")),
    session: Session = Depends(get_session),
) -> ReviewItem:
    item = hydrate_review_item_for_service(session, item_id)
    if not item:
        raise not_found()
    before_json = item.model_dump(mode="json")
    allowed_fields = {"reviewer_notes", "edited_answer_text", "failure_category", "priority"}
    for key, value in payload.items():
        if key not in allowed_fields:
            continue
        if key == "failure_category" and value:
            try:
                value = FailureCategory(value)
            except ValueError:
                raise HTTPException(status_code=422, detail="invalid failure_category")
        setattr(item, key, value)
    item.updated_at = now()
    store.review_items[item.id] = item
    save_review_item_to_database(session, item)
    store.add_audit_log(
        "review_item_updated",
        "ReviewItem",
        str(item.id),
        user_id=user.user_id,
        before_json=before_json,
        after_json=item.model_dump(mode="json"),
    )
    return item


@app.post("/review-items/{item_id}/approve", response_model=ReviewItem)
def post_review_approve(
    item_id: UUID,
    payload: Dict[str, FailureCategory],
    user: CurrentUser = Depends(require_roles("admin", "reviewer")),
    session: Session = Depends(get_session),
) -> ReviewItem:
    if "failure_category" not in payload:
        raise HTTPException(status_code=422, detail="failure_category is required")
    if not hydrate_review_item_for_service(session, item_id):
        raise not_found()
    item = approve_review_item(store, item_id, payload["failure_category"], reviewer_id=user.user_id)
    save_review_item_to_database(session, item)
    return item


@app.post("/review-items/{item_id}/reject", response_model=ReviewItem)
def post_review_reject(
    item_id: UUID,
    payload: Dict[str, FailureCategory],
    user: CurrentUser = Depends(require_roles("admin", "reviewer")),
    session: Session = Depends(get_session),
) -> ReviewItem:
    if "failure_category" not in payload:
        raise HTTPException(status_code=422, detail="failure_category is required")
    if not hydrate_review_item_for_service(session, item_id):
        raise not_found()
    item = reject_review_item(store, item_id, payload["failure_category"], reviewer_id=user.user_id)
    save_review_item_to_database(session, item)
    return item


@app.post("/review-items/{item_id}/source-update-needed", response_model=ReviewItem)
def post_review_source_update_needed(
    item_id: UUID,
    payload: Dict[str, FailureCategory],
    user: CurrentUser = Depends(require_roles("admin", "reviewer")),
    session: Session = Depends(get_session),
) -> ReviewItem:
    if "failure_category" not in payload:
        raise HTTPException(status_code=422, detail="failure_category is required")
    if not hydrate_review_item_for_service(session, item_id):
        raise not_found()
    item = mark_source_update_needed(store, item_id, payload["failure_category"], reviewer_id=user.user_id)
    save_review_item_to_database(session, item)
    return item


@app.post("/review-items/{item_id}/to-faq")
def post_review_to_faq(
    item_id: UUID,
    _user: CurrentUser = Depends(require_roles("admin", "reviewer")),
    session: Session = Depends(get_session),
) -> dict:
    if not hydrate_review_context_for_service(session, item_id):
        raise not_found()
    hydrate_provider_configs(store, session)
    try:
        faq, source, version, artifact, chunks = review_to_faq(store, item_id)
    except KeyError:
        raise not_found()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    save_source_to_database(session, source)
    save_source_version_bundle_to_database(session, version, artifact, chunks)
    save_approved_faq_to_database(session, faq)
    save_review_item_to_database(session, store.review_items[item_id])
    return {"status": "converted_to_faq", "approved_faq": faq, "source": source, "version": version, "chunks": chunks}


@app.post("/review-items/{item_id}/to-eval-case", response_model=EvalCase)
def post_review_to_eval_case(
    item_id: UUID,
    _user: CurrentUser = Depends(require_roles("admin", "reviewer")),
    session: Session = Depends(get_session),
) -> EvalCase:
    if not hydrate_review_context_for_service(session, item_id):
        raise not_found()
    case = review_to_eval_case(store, item_id)
    save_eval_case_to_database(session, case)
    save_review_item_to_database(session, store.review_items[item_id])
    return case


@app.post("/tickets")
def post_ticket(
    payload: TicketCreate,
    _user: CurrentUser = Depends(require_roles("admin", "support")),
    session: Session = Depends(get_session),
) -> dict:
    hydrate_provider_configs(store, session)
    database_product = get_product_from_database(session, payload.product_id) if payload.product_id else None
    if database_product and payload.product_id not in store.products:
        store.products[payload.product_id] = database_product
    if payload.product_id is None or payload.product_id not in store.products:
        raise HTTPException(status_code=422, detail="valid product_id is required")
    source = create_source(
        store,
        SourceCreate(
            product_id=payload.product_id,
            title=payload.title or f"Ticket {payload.external_id or 'import'}",
            source_type=SourceType.ticket_export,
            canonical_uri=f"ticket://{payload.external_id}" if payload.external_id else "",
            trust_level="ticket",
        ),
    )
    version, artifact, chunks = create_source_version(
        store,
        source.id,
        SourceVersionCreate(
            version_label=payload.external_id or "ticket",
            content=f"Title: {payload.title}\n\nStatus: {payload.status}\n\nTags: {', '.join(payload.tags_json)}\n\n{payload.body}",
            parser_version="ticket-v1",
        ),
    )
    ticket = store.add_ticket(Ticket(**payload.model_dump(), source_id=source.id))
    save_source_to_database(session, source)
    save_source_version_bundle_to_database(session, version, artifact, chunks)
    review_item = create_source_issue_review_item_for_failed_version(session, version)
    save_ticket_to_database(session, ticket)
    return {
        "ticket": ticket,
        "source": source,
        "version": version,
        "chunks": chunks,
        "review_item": review_item,
    }


@app.get("/tickets")
def get_tickets(session: Session = Depends(get_session)) -> list[Ticket]:
    return list_tickets_from_database(session) or list(store.tickets.values())


@app.post("/log-sources")
def post_log_source(
    payload: LogSourceCreate,
    _user: CurrentUser = Depends(require_roles("admin", "support")),
    session: Session = Depends(get_session),
) -> dict:
    hydrate_provider_configs(store, session)
    database_product = get_product_from_database(session, payload.product_id) if payload.product_id else None
    if database_product and payload.product_id not in store.products:
        store.products[payload.product_id] = database_product
    if payload.product_id is None or payload.product_id not in store.products:
        raise HTTPException(status_code=422, detail="valid product_id is required")
    source = create_source(
        store,
        SourceCreate(
            product_id=payload.product_id,
            title=f"{payload.log_type or 'Device'} log",
            source_type=SourceType.text_log,
            trust_level="log",
        ),
    )
    version, artifact, chunks = create_source_version(
        store,
        source.id,
        SourceVersionCreate(
            version_label="log",
            content=f"Log type: {payload.log_type}\n\nDevice context: {payload.device_context_json}\n\nTime range: {payload.time_range_json}\n\n{payload.content}",
            parser_version="text-log-v1",
        ),
    )
    log_source = store.add_log_source(LogSource(**payload.model_dump(), source_id=source.id))
    save_source_to_database(session, source)
    save_source_version_bundle_to_database(session, version, artifact, chunks)
    review_item = create_source_issue_review_item_for_failed_version(session, version)
    save_log_source_to_database(session, log_source)
    return {
        "log_source": log_source,
        "source": source,
        "version": version,
        "chunks": chunks,
        "review_item": review_item,
    }


@app.get("/log-sources")
def get_log_sources(session: Session = Depends(get_session)) -> list[LogSource]:
    return list_log_sources_from_database(session) or list(store.log_sources.values())


@app.post("/image-assets")
def post_image_asset(
    payload: ImageAssetCreate,
    _user: CurrentUser = Depends(require_roles("admin", "support")),
    session: Session = Depends(get_session),
) -> dict:
    hydrate_provider_configs(store, session)
    database_product = get_product_from_database(session, payload.product_id) if payload.product_id else None
    if database_product and payload.product_id not in store.products:
        store.products[payload.product_id] = database_product
    if payload.product_id is None or payload.product_id not in store.products:
        raise HTTPException(status_code=422, detail="valid product_id is required")
    source = create_source(
        store,
        SourceCreate(
            product_id=payload.product_id,
            title=f"{payload.image_type or 'Image'} asset",
            source_type=SourceType.image,
            canonical_uri=payload.storage_uri,
            trust_level="image",
        ),
    )
    chunks = []
    version = None
    artifact = None
    if payload.manual_description.strip():
        version, artifact, chunks = create_source_version(
            store,
            source.id,
            SourceVersionCreate(
                version_label="manual-description",
                content=payload.manual_description,
                parser_version="image-description-v1",
            ),
        )
    image_asset = store.add_image_asset(ImageAsset(**payload.model_dump(), source_id=source.id))
    save_source_to_database(session, source)
    if version and artifact:
        save_source_version_bundle_to_database(session, version, artifact, chunks)
    review_item = create_source_issue_review_item_for_failed_version(session, version) if version else None
    save_image_asset_to_database(session, image_asset)
    return {"image_asset": image_asset, "source": source, "version": version, "chunks": chunks, "review_item": review_item}


@app.post("/image-assets/upload")
async def upload_image_asset(
    product_id: UUID = Form(...),
    image_type: str = Form(""),
    manual_description: str = Form(""),
    file: UploadFile = File(...),
    _user: CurrentUser = Depends(require_roles("admin", "support")),
    session: Session = Depends(get_session),
) -> dict:
    hydrate_provider_configs(store, session)
    database_product = get_product_from_database(session, product_id)
    if database_product and product_id not in store.products:
        store.products[product_id] = database_product
    if product_id not in store.products:
        raise HTTPException(status_code=422, detail="valid product_id is required")

    content = await file.read()
    checksum = hashlib.sha256(content).hexdigest()
    filename = file.filename or "image"
    storage = LocalStorageProvider(settings.storage_root)
    storage_uri = storage.save_bytes(f"images/{product_id}/{checksum}-{safe_filename(filename)}", content)
    image_payload = ImageAssetCreate(
        product_id=product_id,
        storage_uri=storage_uri,
        image_type=image_type or "image",
        manual_description=manual_description,
    )
    source = create_source(
        store,
        SourceCreate(
            product_id=product_id,
            title=f"{image_payload.image_type or 'Image'} asset",
            source_type=SourceType.image,
            canonical_uri=storage_uri,
            trust_level="image",
        ),
    )
    chunks = []
    version = None
    artifact = None
    if manual_description.strip():
        version, artifact, chunks = create_source_version(
            store,
            source.id,
            SourceVersionCreate(
                version_label="manual-description",
                content=manual_description,
                parser_version="image-description-v1",
            ),
        )
    image_asset = store.add_image_asset(ImageAsset(**image_payload.model_dump(), source_id=source.id))
    save_source_to_database(session, source)
    if version and artifact:
        save_source_version_bundle_to_database(session, version, artifact, chunks)
    review_item = create_source_issue_review_item_for_failed_version(session, version) if version else None
    save_image_asset_to_database(session, image_asset)
    return {
        "image_asset": image_asset,
        "source": source,
        "version": version,
        "chunks": chunks,
        "review_item": review_item,
        "upload": {
            "filename": filename,
            "mime_type": file.content_type or "application/octet-stream",
            "size_bytes": len(content),
            "checksum": checksum,
        },
    }


@app.get("/image-assets")
def get_image_assets(session: Session = Depends(get_session)) -> list[ImageAsset]:
    return list_image_assets_from_database(session) or list(store.image_assets.values())


@app.get("/image-assets/{image_id}/ocr-results", response_model=list[OcrResult])
def get_image_ocr_results(image_id: UUID, session: Session = Depends(get_session)) -> list[OcrResult]:
    image_asset = store.image_assets.get(image_id) or get_image_asset_from_database(session, image_id)
    if not image_asset:
        raise not_found()
    database_results = list_ocr_results_from_database(session, image_id)
    if database_results:
        return database_results
    return [result for result in store.ocr_results.values() if result.image_asset_id == image_id]


@app.post("/image-assets/{image_id}/ocr")
def post_image_ocr(
    image_id: UUID,
    payload: OcrResultCreate = OcrResultCreate(),
    _user: CurrentUser = Depends(require_roles("admin", "support")),
    session: Session = Depends(get_session),
) -> dict:
    hydrate_provider_configs(store, session)
    image_asset = store.image_assets.get(image_id) or get_image_asset_from_database(session, image_id)
    if not image_asset:
        raise not_found()
    store.image_assets[image_id] = image_asset
    provider_config = store.active_provider_config("ocr")
    ocr_error = ""
    if provider_config and provider_config.provider_name != ocr_provider.provider_name:
        provider_name = provider_config.provider_name
        model_name = provider_config.model_name
        ocr_error = f"OCR provider '{provider_config.provider_name}' is configured but no adapter is installed."
    else:
        provider_result = ocr_provider.ocr(image_asset.storage_uri)
        provider_name = provider_config.provider_name if provider_config else provider_result.provider_name
        model_name = provider_config.model_name if provider_config else provider_result.model_name
        ocr_error = provider_result.error_message
    ocr_text = "" if ocr_error else payload.ocr_text or ""
    ocr_result = store.add_ocr_result(
        OcrResult(
            image_asset_id=image_id,
            provider_name=provider_name,
            model_name=model_name,
            ocr_text=ocr_text,
            confidence=0.0 if ocr_error else payload.confidence,
            status="failed" if ocr_error else "completed",
            error_message=ocr_error,
        )
    )
    chunks = []
    version = None
    artifact = None
    if ocr_text.strip() and image_asset.source_id:
        database_source = get_source_from_database(session, image_asset.source_id)
        if database_source and image_asset.source_id not in store.sources:
            store.sources[image_asset.source_id] = database_source
        if image_asset.source_id not in store.sources:
            raise not_found()
        version, artifact, chunks = create_source_version(
            store,
            image_asset.source_id,
            SourceVersionCreate(version_label="ocr", content=ocr_text, parser_version="fake-ocr-v1"),
        )
    if version and artifact:
        save_source_version_bundle_to_database(session, version, artifact, chunks)
    review_item = create_source_issue_review_item_for_failed_version(session, version) if version else None
    if ocr_error:
        review_item = store.add_review_item(
            ReviewItem(
                source_type="source_issue",
                priority=1,
                failure_category=FailureCategory.generation_error,
                reviewer_notes=ocr_error,
            )
        )
        save_review_item_to_database(session, review_item)
    save_ocr_result_to_database(session, ocr_result)
    return {
        "ocr_result": ocr_result,
        "version": version,
        "chunks": chunks,
        "review_item": review_item,
    }
