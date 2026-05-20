from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile

from app.answers.service import generate_answer
from app.core.config import settings
from app.core.security import CurrentUser, get_current_user, require_roles
from app.db.session import store
from app.eval.runs import run_eval_batch
from app.eval.seeds import seed_eval_cases
from app.ingestion.jobs import retry_ingestion_job as retry_ingestion_job_service
from app.ingestion.jobs import run_ingestion_job
from app.models.schemas import (
    AskRequest,
    AskResponse,
    AuditLog,
    EvalCase,
    EvalCaseCreate,
    FailureCategory,
    ImageAsset,
    ImageAssetCreate,
    IngestionJob,
    IngestionJobCreate,
    LogSource,
    LogSourceCreate,
    OcrResult,
    OcrResultCreate,
    Product,
    ProductAlias,
    ProductAliasCreate,
    ProductCreate,
    ProviderConfig,
    ProviderConfigCreate,
    Question,
    ReviewItem,
    Source,
    SourceCreate,
    SourceType,
    SourceVersionCreate,
    Ticket,
    TicketCreate,
    now,
)
from app.products.service import create_alias, create_product, get_product, list_products
from app.retrieval.entity_extraction import detect_product_aliases
from app.retrieval.query_normalization import normalize_query, product_alias_expansions
from app.retrieval.service import run_retrieval
from app.review.routing import route_answer_for_review
from app.review.service import approve_review_item, reject_review_item, review_to_eval_case, review_to_faq
from app.sources.service import create_source, create_source_version, create_uploaded_source_version, list_sources
from app.providers.ocr import ocr_provider

app = FastAPI(title=settings.app_name, version="0.1.0")


def not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="not found")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "boardpilot-api"}


@app.get("/version")
def version() -> dict:
    return {"version": "0.1.0", "environment": settings.environment}


@app.get("/providers")
def providers() -> dict:
    return {
        "llm": settings.llm_provider,
        "embedding": settings.embedding_provider,
        "reranker": settings.reranker_provider,
        "ocr": settings.ocr_provider,
        "configs": list(store.provider_configs.values()),
    }


@app.get("/me", response_model=CurrentUser)
def me(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    return user


@app.post("/provider-configs", response_model=ProviderConfig)
def post_provider_config(
    payload: ProviderConfigCreate,
    user: CurrentUser = Depends(require_roles("admin")),
) -> ProviderConfig:
    return store.add_provider_config(ProviderConfig(**payload.model_dump()), user_id=user.user_id)


@app.get("/provider-configs", response_model=list[ProviderConfig])
def get_provider_configs(_user: CurrentUser = Depends(require_roles("admin"))) -> list[ProviderConfig]:
    return list(store.provider_configs.values())


@app.patch("/provider-configs/{config_id}", response_model=ProviderConfig)
def patch_provider_config(
    config_id: UUID,
    payload: Dict[str, Any],
    user: CurrentUser = Depends(require_roles("admin")),
) -> ProviderConfig:
    if config_id not in store.provider_configs:
        raise not_found()
    config = store.provider_configs[config_id]
    before_json = config.model_dump(mode="json")
    allowed_fields = {"provider_type", "provider_name", "model_name", "config_json", "enabled"}
    for key, value in payload.items():
        if key in allowed_fields:
            setattr(config, key, value)
    store.provider_configs[config_id] = config
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
) -> dict:
    if config_id not in store.provider_configs:
        raise not_found()
    config = store.provider_configs.pop(config_id)
    store.add_audit_log(
        "provider_config_deleted",
        "ProviderConfig",
        str(config.id),
        user_id=user.user_id,
        before_json=config.model_dump(mode="json"),
    )
    return {"status": "deleted"}


@app.post("/products", response_model=Product)
def post_product(payload: ProductCreate, _user: CurrentUser = Depends(require_roles("admin"))) -> Product:
    return create_product(store, payload)


@app.get("/products", response_model=list[Product])
def get_products() -> list[Product]:
    return list_products(store)


@app.get("/products/{product_id}", response_model=Product)
def get_product_endpoint(product_id: UUID) -> Product:
    try:
        return get_product(store, product_id)
    except KeyError:
        raise not_found()


@app.patch("/products/{product_id}", response_model=Product)
def patch_product(product_id: UUID, payload: Dict[str, Any], _user: CurrentUser = Depends(require_roles("admin"))) -> Product:
    if product_id not in store.products:
        raise not_found()
    product = store.products[product_id]
    for key, value in payload.items():
        if hasattr(product, key):
            setattr(product, key, value)
    store.products[product_id] = product
    return product


@app.post("/products/{product_id}/aliases", response_model=ProductAlias)
def post_alias(
    product_id: UUID,
    payload: ProductAliasCreate,
    _user: CurrentUser = Depends(require_roles("admin", "support")),
) -> ProductAlias:
    try:
        return create_alias(store, product_id, payload)
    except KeyError:
        raise not_found()


@app.get("/products/{product_id}/aliases", response_model=list[ProductAlias])
def get_aliases(product_id: UUID) -> list[ProductAlias]:
    return store.aliases_for_product(product_id)


@app.post("/sources", response_model=Source)
def post_source(payload: SourceCreate, _user: CurrentUser = Depends(require_roles("admin", "support"))) -> Source:
    try:
        return create_source(store, payload)
    except KeyError:
        raise not_found()


@app.get("/sources", response_model=list[Source])
def get_sources() -> list[Source]:
    return list_sources(store)


@app.get("/sources/{source_id}", response_model=Source)
def get_source(source_id: UUID) -> Source:
    if source_id not in store.sources:
        raise not_found()
    return store.sources[source_id]


@app.patch("/sources/{source_id}", response_model=Source)
def patch_source(
    source_id: UUID,
    payload: Dict[str, Any],
    user: CurrentUser = Depends(require_roles("admin", "support")),
) -> Source:
    if source_id not in store.sources:
        raise not_found()
    source = store.sources[source_id]
    before = source.model_dump(mode="json")
    for key, value in payload.items():
        if hasattr(source, key):
            setattr(source, key, value)
    store.sources[source_id] = source
    store.add_audit_log(
        "source_updated",
        "Source",
        str(source.id),
        user_id=user.user_id,
        before_json=before,
        after_json=source.model_dump(mode="json"),
    )
    return source


@app.post("/sources/{source_id}/versions")
def post_source_version(
    source_id: UUID,
    payload: SourceVersionCreate,
    _user: CurrentUser = Depends(require_roles("admin", "support")),
) -> dict:
    try:
        version, artifact, chunks = create_source_version(store, source_id, payload)
    except KeyError:
        raise not_found()
    return {"version": version, "artifact": artifact, "chunks": chunks}


@app.post("/sources/{source_id}/versions/upload")
async def upload_source_version(
    source_id: UUID,
    version_label: str = Form("uploaded"),
    file: UploadFile = File(...),
    _user: CurrentUser = Depends(require_roles("admin", "support")),
) -> dict:
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
    return {"version": version, "artifact": artifact, "chunks": chunks}


@app.get("/sources/{source_id}/versions")
def get_source_versions(source_id: UUID) -> list:
    return [version for version in store.source_versions.values() if version.source_id == source_id]


@app.post("/sources/{source_id}/versions/{version_id}/artifacts")
def post_source_artifact(
    source_id: UUID,
    version_id: UUID,
    payload: SourceVersionCreate,
    _user: CurrentUser = Depends(require_roles("admin", "support")),
) -> dict:
    if source_id not in store.sources or version_id not in store.source_versions:
        raise not_found()
    version, artifact, chunks = create_source_version(store, source_id, payload)
    return {"version": version, "artifact": artifact, "chunks": chunks}


@app.get("/source-versions/{version_id}/chunks")
def get_chunks(version_id: UUID) -> list:
    return [chunk for chunk in store.chunks.values() if chunk.source_version_id == version_id]


@app.get("/chunks/{chunk_id}/embeddings")
def get_chunk_embeddings(chunk_id: UUID) -> list:
    if chunk_id not in store.chunks:
        raise not_found()
    return store.embeddings_for_chunk(chunk_id)


@app.post("/ingestion/jobs")
def post_ingestion_job(
    payload: IngestionJobCreate,
    _user: CurrentUser = Depends(require_roles("admin", "support")),
) -> dict:
    if payload.source_version_id not in store.source_versions:
        raise not_found()
    job, chunks = run_ingestion_job(payload.source_version_id)
    return {"job": job, "chunks": chunks}


@app.get("/ingestion/jobs")
def get_ingestion_jobs() -> list[IngestionJob]:
    return list(store.ingestion_jobs.values())


@app.get("/ingestion/jobs/{job_id}")
def get_ingestion_job(job_id: UUID) -> IngestionJob:
    if job_id not in store.ingestion_jobs:
        raise not_found()
    return store.ingestion_jobs[job_id]


@app.post("/ingestion/jobs/{job_id}/retry")
def retry_ingestion_job(job_id: UUID, _user: CurrentUser = Depends(require_roles("admin", "support"))) -> dict:
    if job_id not in store.ingestion_jobs:
        raise not_found()
    job, chunks = retry_ingestion_job_service(job_id)
    return {"job": job, "chunks": chunks}


@app.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest) -> AskResponse:
    detected_entities = detect_product_aliases(store, payload.question)
    normalized_query = normalize_query(payload.question, product_alias_expansions(detected_entities))
    question = store.add_question(
        Question(
            product_id=payload.product_id,
            raw_text=payload.question,
            normalized_text=normalized_query,
            detected_entities_json=detected_entities,
            metadata_filters_json=payload.metadata_filters_json,
        )
    )
    retrieval_run, candidates, evidence = run_retrieval(store, question)
    answer = generate_answer(store, question, retrieval_run.id, evidence)
    review_item = route_answer_for_review(answer)
    if review_item:
        review_item = store.add_review_item(review_item)
    return AskResponse(
        question=question,
        retrieval_run=retrieval_run,
        candidates=candidates,
        evidence=evidence,
        answer=answer,
        review_item=review_item,
    )


@app.get("/questions/{question_id}")
def get_question(question_id: UUID) -> Question:
    if question_id not in store.questions:
        raise not_found()
    return store.questions[question_id]


@app.get("/retrieval-runs/{run_id}")
def get_retrieval_run(run_id: UUID):
    if run_id not in store.retrieval_runs:
        raise not_found()
    return store.retrieval_runs[run_id]


@app.get("/retrieval-runs/{run_id}/candidates")
def get_retrieval_candidates(run_id: UUID) -> list:
    return store.candidates_for_run(run_id)


@app.get("/answers/{answer_id}")
def get_answer(answer_id: UUID):
    if answer_id not in store.answers:
        raise not_found()
    return store.answers[answer_id]


@app.get("/answers/{answer_id}/evidence")
def get_answer_evidence(answer_id: UUID) -> list:
    if answer_id not in store.answers:
        raise not_found()
    answer = store.answers[answer_id]
    return store.evidence_for_run(answer.retrieval_run_id)


@app.get("/model-runs/{model_run_id}")
def get_model_run(model_run_id: UUID):
    if model_run_id not in store.model_runs:
        raise not_found()
    return store.model_runs[model_run_id]


@app.post("/answers/{answer_id}/feedback")
def post_feedback(answer_id: UUID, payload: Dict[str, Any], _user: CurrentUser = Depends(get_current_user)) -> ReviewItem:
    if answer_id not in store.answers:
        raise not_found()
    answer = store.answers[answer_id]
    item = ReviewItem(
        source_type=payload.get("feedback_type", "user_feedback"),
        question_id=answer.question_id,
        answer_id=answer.id,
        reviewer_notes=payload.get("notes", ""),
    )
    return store.add_review_item(item)


@app.post("/eval-cases", response_model=EvalCase)
def post_eval_case(
    payload: EvalCaseCreate,
    _user: CurrentUser = Depends(require_roles("admin", "support", "reviewer")),
) -> EvalCase:
    return store.add_eval_case(EvalCase(**payload.model_dump()))


@app.get("/eval-cases", response_model=list[EvalCase])
def get_eval_cases() -> list[EvalCase]:
    return list(store.eval_cases.values())


@app.post("/eval-cases/seed")
def post_seed_eval_cases(_user: CurrentUser = Depends(require_roles("admin", "support", "reviewer"))) -> dict:
    product, source, cases = seed_eval_cases(store)
    return {"product": product, "source": source, "cases": cases, "case_count": len(cases)}


@app.get("/eval-cases/{case_id}", response_model=EvalCase)
def get_eval_case(case_id: UUID) -> EvalCase:
    if case_id not in store.eval_cases:
        raise not_found()
    return store.eval_cases[case_id]


@app.patch("/eval-cases/{case_id}", response_model=EvalCase)
def patch_eval_case(
    case_id: UUID,
    payload: Dict[str, Any],
    user: CurrentUser = Depends(require_roles("admin", "support", "reviewer")),
) -> EvalCase:
    if case_id not in store.eval_cases:
        raise not_found()
    case = store.eval_cases[case_id]
    before = case.model_dump(mode="json")
    for key, value in payload.items():
        if hasattr(case, key):
            setattr(case, key, value)
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
) -> dict:
    run, results = run_eval_batch(store, (payload or {}).get("name", "MVP eval"))
    return {"eval_run": run, "results": results}


@app.get("/eval-runs")
def get_eval_runs() -> list:
    return list(store.eval_runs.values())


@app.get("/eval-runs/compare")
def compare_eval_runs(run_a: UUID, run_b: UUID) -> dict:
    if run_a not in store.eval_runs or run_b not in store.eval_runs:
        raise not_found()
    baseline = store.eval_runs[run_a]
    candidate = store.eval_runs[run_b]
    deltas = {}
    for key, candidate_value in candidate.summary_metrics_json.items():
        baseline_value = baseline.summary_metrics_json.get(key)
        if isinstance(candidate_value, (int, float)) and isinstance(baseline_value, (int, float)):
            deltas[key] = candidate_value - baseline_value
    return {"baseline": baseline, "candidate": candidate, "deltas": deltas}


@app.get("/eval-runs/{run_id}")
def get_eval_run(run_id: UUID):
    if run_id not in store.eval_runs:
        raise not_found()
    return store.eval_runs[run_id]


@app.get("/eval-runs/{run_id}/results")
def get_eval_results(run_id: UUID) -> list:
    return [result for result in store.eval_results.values() if result.eval_run_id == run_id]


@app.post("/eval-results/{result_id}/to-review")
def eval_result_to_review(
    result_id: UUID,
    _user: CurrentUser = Depends(require_roles("admin", "support", "reviewer")),
) -> ReviewItem:
    if result_id not in store.eval_results:
        raise not_found()
    result = store.eval_results[result_id]
    return store.add_review_item(
        ReviewItem(
            source_type="eval_failure",
            question_id=result.question_id,
            answer_id=result.answer_id,
            eval_result_id=result.id,
            failure_category=result.failure_category,
        )
    )


@app.get("/review-items", response_model=list[ReviewItem])
def get_review_items() -> list[ReviewItem]:
    return list(store.review_items.values())


@app.get("/review-items/{item_id}", response_model=ReviewItem)
def get_review_item(item_id: UUID) -> ReviewItem:
    if item_id not in store.review_items:
        raise not_found()
    return store.review_items[item_id]


@app.get("/audit-logs", response_model=list[AuditLog])
def get_audit_logs(_user: CurrentUser = Depends(require_roles("admin"))) -> list[AuditLog]:
    return list(store.audit_logs.values())


@app.patch("/review-items/{item_id}", response_model=ReviewItem)
def patch_review_item(
    item_id: UUID,
    payload: Dict[str, Any],
    user: CurrentUser = Depends(require_roles("admin", "reviewer")),
) -> ReviewItem:
    if item_id not in store.review_items:
        raise not_found()
    item = store.review_items[item_id]
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
) -> ReviewItem:
    if "failure_category" not in payload:
        raise HTTPException(status_code=422, detail="failure_category is required")
    return approve_review_item(store, item_id, payload["failure_category"], reviewer_id=user.user_id)


@app.post("/review-items/{item_id}/reject", response_model=ReviewItem)
def post_review_reject(
    item_id: UUID,
    payload: Dict[str, FailureCategory],
    user: CurrentUser = Depends(require_roles("admin", "reviewer")),
) -> ReviewItem:
    if "failure_category" not in payload:
        raise HTTPException(status_code=422, detail="failure_category is required")
    return reject_review_item(store, item_id, payload["failure_category"], reviewer_id=user.user_id)


@app.post("/review-items/{item_id}/to-faq")
def post_review_to_faq(item_id: UUID, _user: CurrentUser = Depends(require_roles("admin", "reviewer"))) -> dict:
    try:
        faq, source, chunks = review_to_faq(store, item_id)
    except KeyError:
        raise not_found()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"status": "converted_to_faq", "approved_faq": faq, "source": source, "chunks": chunks}


@app.post("/review-items/{item_id}/to-eval-case", response_model=EvalCase)
def post_review_to_eval_case(
    item_id: UUID,
    _user: CurrentUser = Depends(require_roles("admin", "reviewer")),
) -> EvalCase:
    return review_to_eval_case(store, item_id)


@app.post("/tickets")
def post_ticket(payload: TicketCreate, _user: CurrentUser = Depends(require_roles("admin", "support"))) -> dict:
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
    version, _artifact, chunks = create_source_version(
        store,
        source.id,
        SourceVersionCreate(
            version_label=payload.external_id or "ticket",
            content=f"Title: {payload.title}\n\nStatus: {payload.status}\n\nTags: {', '.join(payload.tags_json)}\n\n{payload.body}",
            parser_version="ticket-v1",
        ),
    )
    ticket = store.add_ticket(Ticket(**payload.model_dump(), source_id=source.id))
    return {"ticket": ticket, "source": source, "version": version, "chunks": chunks}


@app.get("/tickets")
def get_tickets() -> list[Ticket]:
    return list(store.tickets.values())


@app.post("/log-sources")
def post_log_source(payload: LogSourceCreate, _user: CurrentUser = Depends(require_roles("admin", "support"))) -> dict:
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
    version, _artifact, chunks = create_source_version(
        store,
        source.id,
        SourceVersionCreate(
            version_label="log",
            content=f"Log type: {payload.log_type}\n\nDevice context: {payload.device_context_json}\n\nTime range: {payload.time_range_json}\n\n{payload.content}",
            parser_version="text-log-v1",
        ),
    )
    log_source = store.add_log_source(LogSource(**payload.model_dump(), source_id=source.id))
    return {"log_source": log_source, "source": source, "version": version, "chunks": chunks}


@app.get("/log-sources")
def get_log_sources() -> list[LogSource]:
    return list(store.log_sources.values())


@app.post("/image-assets")
def post_image_asset(payload: ImageAssetCreate, _user: CurrentUser = Depends(require_roles("admin", "support"))) -> dict:
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
    if payload.manual_description.strip():
        version, _artifact, chunks = create_source_version(
            store,
            source.id,
            SourceVersionCreate(
                version_label="manual-description",
                content=payload.manual_description,
                parser_version="image-description-v1",
            ),
        )
    image_asset = store.add_image_asset(ImageAsset(**payload.model_dump(), source_id=source.id))
    return {"image_asset": image_asset, "source": source, "version": version, "chunks": chunks}


@app.get("/image-assets")
def get_image_assets() -> list[ImageAsset]:
    return list(store.image_assets.values())


@app.post("/image-assets/{image_id}/ocr")
def post_image_ocr(
    image_id: UUID,
    payload: OcrResultCreate = OcrResultCreate(),
    _user: CurrentUser = Depends(require_roles("admin", "support")),
) -> dict:
    if image_id not in store.image_assets:
        raise not_found()
    image_asset = store.image_assets[image_id]
    provider_result = ocr_provider.ocr(image_asset.storage_uri)
    ocr_text = payload.ocr_text or ""
    ocr_result = store.add_ocr_result(
        OcrResult(
            image_asset_id=image_id,
            provider_name=provider_result.provider_name,
            model_name=provider_result.model_name,
            ocr_text=ocr_text,
            confidence=payload.confidence,
        )
    )
    chunks = []
    version = None
    if ocr_text.strip() and image_asset.source_id:
        version, _artifact, chunks = create_source_version(
            store,
            image_asset.source_id,
            SourceVersionCreate(version_label="ocr", content=ocr_text, parser_version="fake-ocr-v1"),
        )
    return {"ocr_result": ocr_result, "version": version, "chunks": chunks}
