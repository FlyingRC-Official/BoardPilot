from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from app.answers.service import generate_answer
from app.core.config import settings
from app.db.session import store
from app.eval.runs import run_eval_batch
from app.eval.seeds import seed_eval_cases
from app.ingestion.tasks import ingest_source_version
from app.models.schemas import (
    AskRequest,
    AskResponse,
    EvalCase,
    EvalCaseCreate,
    FailureCategory,
    Product,
    ProductAlias,
    ProductAliasCreate,
    ProductCreate,
    Question,
    ReviewItem,
    Source,
    SourceCreate,
    SourceVersionCreate,
)
from app.products.service import create_alias, create_product, get_product, list_products
from app.retrieval.query_normalization import normalize_query
from app.retrieval.service import run_retrieval
from app.review.routing import route_answer_for_review
from app.review.service import approve_review_item, reject_review_item, review_to_eval_case, review_to_faq
from app.sources.service import create_source, create_source_version, create_uploaded_source_version, list_sources

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
    }


@app.post("/products", response_model=Product)
def post_product(payload: ProductCreate) -> Product:
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
def patch_product(product_id: UUID, payload: Dict[str, Any]) -> Product:
    if product_id not in store.products:
        raise not_found()
    product = store.products[product_id]
    for key, value in payload.items():
        if hasattr(product, key):
            setattr(product, key, value)
    store.products[product_id] = product
    return product


@app.post("/products/{product_id}/aliases", response_model=ProductAlias)
def post_alias(product_id: UUID, payload: ProductAliasCreate) -> ProductAlias:
    try:
        return create_alias(store, product_id, payload)
    except KeyError:
        raise not_found()


@app.get("/products/{product_id}/aliases", response_model=list[ProductAlias])
def get_aliases(product_id: UUID) -> list[ProductAlias]:
    return store.aliases_for_product(product_id)


@app.post("/sources", response_model=Source)
def post_source(payload: SourceCreate) -> Source:
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
def patch_source(source_id: UUID, payload: Dict[str, Any]) -> Source:
    if source_id not in store.sources:
        raise not_found()
    source = store.sources[source_id]
    for key, value in payload.items():
        if hasattr(source, key):
            setattr(source, key, value)
    store.sources[source_id] = source
    return source


@app.post("/sources/{source_id}/versions")
def post_source_version(source_id: UUID, payload: SourceVersionCreate) -> dict:
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
def post_source_artifact(source_id: UUID, version_id: UUID, payload: SourceVersionCreate) -> dict:
    if source_id not in store.sources or version_id not in store.source_versions:
        raise not_found()
    version, artifact, chunks = create_source_version(store, source_id, payload)
    return {"version": version, "artifact": artifact, "chunks": chunks}


@app.get("/source-versions/{version_id}/chunks")
def get_chunks(version_id: UUID) -> list:
    return [chunk for chunk in store.chunks.values() if chunk.source_version_id == version_id]


@app.post("/ingestion/jobs")
def post_ingestion_job(payload: Dict[str, UUID]) -> dict:
    chunks = ingest_source_version(store, payload["source_version_id"])
    return {"status": "completed", "chunk_count": len(chunks)}


@app.get("/ingestion/jobs")
def get_ingestion_jobs() -> list:
    return []


@app.get("/ingestion/jobs/{job_id}")
def get_ingestion_job(job_id: UUID) -> dict:
    return {"id": job_id, "status": "completed"}


@app.post("/ingestion/jobs/{job_id}/retry")
def retry_ingestion_job(job_id: UUID) -> dict:
    return {"id": job_id, "status": "retry_not_required_for_inline_mvp"}


@app.post("/ask", response_model=AskResponse)
def ask(payload: AskRequest) -> AskResponse:
    question = store.add_question(
        Question(
            product_id=payload.product_id,
            raw_text=payload.question,
            normalized_text=normalize_query(payload.question),
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


@app.post("/answers/{answer_id}/feedback")
def post_feedback(answer_id: UUID, payload: Dict[str, Any]) -> ReviewItem:
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
def post_eval_case(payload: EvalCaseCreate) -> EvalCase:
    return store.add_eval_case(EvalCase(**payload.model_dump()))


@app.get("/eval-cases", response_model=list[EvalCase])
def get_eval_cases() -> list[EvalCase]:
    return list(store.eval_cases.values())


@app.post("/eval-cases/seed")
def post_seed_eval_cases() -> dict:
    product, source, cases = seed_eval_cases(store)
    return {"product": product, "source": source, "cases": cases, "case_count": len(cases)}


@app.get("/eval-cases/{case_id}", response_model=EvalCase)
def get_eval_case(case_id: UUID) -> EvalCase:
    if case_id not in store.eval_cases:
        raise not_found()
    return store.eval_cases[case_id]


@app.patch("/eval-cases/{case_id}", response_model=EvalCase)
def patch_eval_case(case_id: UUID, payload: Dict[str, Any]) -> EvalCase:
    if case_id not in store.eval_cases:
        raise not_found()
    case = store.eval_cases[case_id]
    for key, value in payload.items():
        if hasattr(case, key):
            setattr(case, key, value)
    return case


@app.post("/eval-runs")
def post_eval_run(payload: Optional[Dict[str, Any]] = None) -> dict:
    run, results = run_eval_batch(store, (payload or {}).get("name", "MVP eval"))
    return {"eval_run": run, "results": results}


@app.get("/eval-runs")
def get_eval_runs() -> list:
    return list(store.eval_runs.values())


@app.get("/eval-runs/{run_id}")
def get_eval_run(run_id: UUID):
    if run_id not in store.eval_runs:
        raise not_found()
    return store.eval_runs[run_id]


@app.get("/eval-runs/{run_id}/results")
def get_eval_results(run_id: UUID) -> list:
    return [result for result in store.eval_results.values() if result.eval_run_id == run_id]


@app.post("/eval-results/{result_id}/to-review")
def eval_result_to_review(result_id: UUID) -> ReviewItem:
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


@app.patch("/review-items/{item_id}", response_model=ReviewItem)
def patch_review_item(item_id: UUID, payload: Dict[str, Any]) -> ReviewItem:
    if item_id not in store.review_items:
        raise not_found()
    item = store.review_items[item_id]
    for key, value in payload.items():
        if hasattr(item, key):
            setattr(item, key, value)
    return item


@app.post("/review-items/{item_id}/approve", response_model=ReviewItem)
def post_review_approve(item_id: UUID, payload: Dict[str, FailureCategory]) -> ReviewItem:
    return approve_review_item(store, item_id, payload.get("failure_category", FailureCategory.human_policy_required))


@app.post("/review-items/{item_id}/reject", response_model=ReviewItem)
def post_review_reject(item_id: UUID, payload: Dict[str, FailureCategory]) -> ReviewItem:
    return reject_review_item(store, item_id, payload.get("failure_category", FailureCategory.human_policy_required))


@app.post("/review-items/{item_id}/to-faq")
def post_review_to_faq(item_id: UUID) -> dict:
    try:
        faq, source, chunks = review_to_faq(store, item_id)
    except KeyError:
        raise not_found()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"status": "converted_to_faq", "approved_faq": faq, "source": source, "chunks": chunks}


@app.post("/review-items/{item_id}/to-eval-case", response_model=EvalCase)
def post_review_to_eval_case(item_id: UUID) -> EvalCase:
    return review_to_eval_case(store, item_id)


@app.post("/tickets")
def post_ticket(payload: Dict[str, Any]) -> dict:
    store.tickets.append(payload)
    return payload


@app.get("/tickets")
def get_tickets() -> list[dict]:
    return store.tickets


@app.post("/log-sources")
def post_log_source(payload: Dict[str, Any]) -> dict:
    store.log_sources.append(payload)
    return payload


@app.get("/log-sources")
def get_log_sources() -> list[dict]:
    return store.log_sources


@app.post("/image-assets")
def post_image_asset(payload: Dict[str, Any]) -> dict:
    store.image_assets.append(payload)
    return payload


@app.get("/image-assets")
def get_image_assets() -> list[dict]:
    return store.image_assets


@app.post("/image-assets/{image_id}/ocr")
def post_image_ocr(image_id: UUID) -> dict:
    return {"image_asset_id": image_id, "provider_name": "fake", "model_name": "fake-ocr-placeholder", "ocr_text": ""}
