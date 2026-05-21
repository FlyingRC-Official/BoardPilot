from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

import app.models.orm  # noqa: F401
from app.core.security import CurrentUser
from app.db.base import Base
from app.db.repositories import CatalogRepository, RetrievalRepository, ReviewEvalRepository, RuntimeRepository
from app.db.store import InMemoryStore
from app.providers.config_store import hydrate_provider_configs
from app.retrieval.catalog import hydrate_retrieval_catalog
from app.retrieval.service import run_retrieval
from app.main import (
    compare_eval_runs,
    delete_provider_config_from_database,
    get_answer_from_database,
    get_answer_evidence,
    get_artifact_from_database,
    get_approved_faq_from_database,
    get_chunk_from_database,
    get_eval_case_from_database,
    get_eval_result_from_database,
    get_eval_run_from_database,
    eval_result_to_review,
    get_image_asset_from_database,
    get_image_ocr_results,
    get_model_run_from_database,
    get_provider_config_from_database,
    get_product_from_database,
    get_question_from_database,
    get_retrieval_run_from_database,
    get_review_item_from_database,
    get_review_item_detail,
    get_runtime_job,
    get_source_from_database,
    get_source_version_from_database,
    hydrate_source_version_for_service,
    hydrate_review_context_for_service,
    hydrate_review_item_for_service,
    list_aliases_from_database,
    list_artifacts_from_database,
    list_audit_logs_from_database,
    list_chunk_embeddings_from_database,
    list_chunks_from_database,
    list_eval_cases_from_database,
    list_eval_results_from_database,
    list_eval_runs_from_database,
    list_evidence_from_database,
    list_image_assets_from_database,
    list_log_sources_from_database,
    list_ocr_results_from_database,
    list_provider_configs_from_database,
    list_products_from_database,
    list_question_attachments_from_database,
    list_retrieval_candidates_from_database,
    list_review_items_from_database,
    list_runtime_jobs,
    list_sources_from_database,
    list_source_versions_from_database,
    list_tickets_from_database,
    post_feedback,
    post_image_ocr,
    patch_eval_case,
    retry_ingestion_job,
    save_alias_to_database,
    save_ask_response_to_database,
    save_approved_faq_to_database,
    save_chunk_embeddings_to_database,
    save_chunks_to_database,
    save_eval_case_to_database,
    save_eval_run_results_to_database,
    save_image_asset_to_database,
    save_log_source_to_database,
    save_ocr_result_to_database,
    save_provider_config_to_database,
    save_product_to_database,
    save_question_attachment_to_database,
    save_review_item_to_database,
    save_runtime_job,
    save_source_to_database,
    save_source_version_bundle_to_database,
    save_source_version_to_database,
    save_ticket_to_database,
)
from app.models.schemas import (
    Answer,
    AnswerFeedbackCreate,
    ApprovedFAQ,
    AuditLog,
    Chunk,
    ChunkEmbedding,
    EvalCase,
    EvalCasePatch,
    EvalResult,
    EvalRun,
    Evidence,
    EvidenceSufficiency,
    FailureCategory,
    ImageAsset,
    IngestionJob,
    LogSource,
    ModelRun,
    OcrResult,
    OcrResultCreate,
    Product,
    ProductAlias,
    ProviderConfig,
    Question,
    QuestionAttachment,
    RetrievalCandidate,
    RetrievalRun,
    ReviewItem,
    ReviewStatus,
    Source,
    SourceArtifact,
    SourceType,
    SourceVersion,
    Ticket,
)
from app.providers.base import OCRResult


def test_sqlalchemy_metadata_covers_required_tables():
    required_tables = {
        "products",
        "product_aliases",
        "sources",
        "source_versions",
        "source_artifacts",
        "chunks",
        "chunk_embeddings",
        "questions",
        "question_attachments",
        "retrieval_runs",
        "retrieval_candidates",
        "evidences",
        "answers",
        "eval_cases",
        "eval_runs",
        "eval_results",
        "review_items",
        "approved_faqs",
        "tickets",
        "log_sources",
        "image_assets",
        "ocr_results",
        "provider_configs",
        "model_runs",
        "audit_logs",
        "ingestion_jobs",
    }
    assert required_tables <= set(Base.metadata.tables)


def test_review_item_source_type_is_limited_to_documented_buckets():
    accepted = {
        "low_confidence_answer",
        "insufficient_evidence",
        "user_feedback",
        "eval_failure",
        "source_issue",
    }

    for source_type in accepted:
        assert ReviewItem(source_type=source_type).source_type == source_type

    with pytest.raises(ValidationError):
        ReviewItem(source_type="generation_error")


def test_sqlalchemy_schema_can_create_core_tables_in_sqlite():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_subset = [
        Base.metadata.tables["products"],
        Base.metadata.tables["product_aliases"],
        Base.metadata.tables["sources"],
        Base.metadata.tables["source_versions"],
        Base.metadata.tables["source_artifacts"],
        Base.metadata.tables["chunks"],
        Base.metadata.tables["questions"],
        Base.metadata.tables["retrieval_runs"],
        Base.metadata.tables["retrieval_candidates"],
        Base.metadata.tables["evidences"],
        Base.metadata.tables["model_runs"],
        Base.metadata.tables["answers"],
        Base.metadata.tables["review_items"],
        Base.metadata.tables["audit_logs"],
    ]
    Base.metadata.create_all(bind=engine, tables=create_subset)
    table_names = set(inspect(engine).get_table_names())
    assert "products" in table_names
    assert "answers" in table_names
    assert "audit_logs" in table_names
    source_artifact_columns = {column["name"] for column in inspect(engine).get_columns("source_artifacts")}
    assert "content" in source_artifact_columns


def test_catalog_repository_round_trips_source_records_in_sqlite():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_subset = [
        Base.metadata.tables["products"],
        Base.metadata.tables["product_aliases"],
        Base.metadata.tables["sources"],
        Base.metadata.tables["source_versions"],
        Base.metadata.tables["source_artifacts"],
        Base.metadata.tables["chunks"],
        Base.metadata.tables["chunk_embeddings"],
    ]
    Base.metadata.create_all(bind=engine, tables=create_subset)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    repo = CatalogRepository(session)

    product = repo.add_product(Product(name="FlyingRC F4", slug="flyingrc-f4", description="Flight controller"))
    alias = repo.add_alias(ProductAlias(product_id=product.id, alias="F4 FC", confidence=0.9))
    source = repo.add_source(
        Source(product_id=product.id, title="FlyingRC F4 Manual", source_type=SourceType.markdown, trust_level="official")
    )
    version = repo.add_source_version(
        SourceVersion(source_id=source.id, version_label="v1", content_hash="a" * 64, parser_version="mvp-markdown-parser-v1")
    )
    artifact = repo.add_artifact(
        SourceArtifact(
            source_version_id=version.id,
            storage_uri="memory://manual",
            checksum="a" * 64,
            metadata_json={"source_type": "markdown"},
            content="USB power is for configuration only.",
        )
    )
    chunk = repo.add_chunks(
        [
            Chunk(
                source_version_id=version.id,
                product_id=product.id,
                chunk_index=0,
                content=artifact.content,
                content_hash="b" * 64,
                token_count=6,
            )
        ]
    )[0]
    session.commit()
    session.expire_all()

    assert repo.list_products()[0].id == product.id
    assert repo.aliases_for_product(product.id)[0].id == alias.id
    assert repo.list_sources()[0].source_type == SourceType.markdown
    assert repo.versions_for_source(source.id)[0].id == version.id
    assert repo.artifacts_for_version(version.id)[0].content == artifact.content
    assert repo.chunks_for_version(version.id)[0].id == chunk.id


def test_runtime_repository_round_trips_worker_and_audit_records_in_sqlite():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_subset = [
        Base.metadata.tables["products"],
        Base.metadata.tables["sources"],
        Base.metadata.tables["source_versions"],
        Base.metadata.tables["ingestion_jobs"],
        Base.metadata.tables["audit_logs"],
    ]
    Base.metadata.create_all(bind=engine, tables=create_subset)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    catalog_repo = CatalogRepository(session)
    runtime_repo = RuntimeRepository(session)

    product = catalog_repo.add_product(Product(name="FlyingRC F4", slug="flyingrc-f4", description="Flight controller"))
    source = catalog_repo.add_source(Source(product_id=product.id, title="Manual", source_type=SourceType.markdown))
    version = catalog_repo.add_source_version(SourceVersion(source_id=source.id, version_label="v1", content_hash="c" * 64))
    job = runtime_repo.add_ingestion_job(IngestionJob(source_version_id=version.id))
    job.status = "completed"
    job.chunk_count = 2
    runtime_repo.add_ingestion_job(job)
    audit = runtime_repo.add_audit_log(
        AuditLog(
            user_id="worker",
            action="ingestion_completed",
            entity_type="IngestionJob",
            entity_id=str(job.id),
            after_json={"chunk_count": 2},
        )
    )
    session.commit()
    session.expire_all()

    assert runtime_repo.get_ingestion_job(job.id).status == "completed"
    assert runtime_repo.list_ingestion_jobs()[0].chunk_count == 2
    assert runtime_repo.list_audit_logs()[0].id == audit.id
    assert runtime_repo.list_audit_logs()[0].after_json == {"chunk_count": 2}
    assert list_audit_logs_from_database(session)[0].id == audit.id


def test_retry_ingestion_job_prefers_database_job_over_stale_memory():
    import app.main as main_app

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    catalog_repo = CatalogRepository(session)
    runtime_repo = RuntimeRepository(session)

    product = catalog_repo.add_product(Product(name="FlyingRC F4", slug="flyingrc-f4", description="Flight controller"))
    source = catalog_repo.add_source(Source(product_id=product.id, title="Manual", source_type=SourceType.markdown))
    database_version = catalog_repo.add_source_version(SourceVersion(source_id=source.id, version_label="db", content_hash="d" * 64))
    stale_version = catalog_repo.add_source_version(SourceVersion(source_id=source.id, version_label="stale", content_hash="e" * 64))
    catalog_repo.add_artifact(
        SourceArtifact(source_version_id=database_version.id, storage_uri="memory://db", content="Database retry content.")
    )
    catalog_repo.add_artifact(
        SourceArtifact(source_version_id=stale_version.id, storage_uri="memory://stale", content="Stale retry content.")
    )
    database_job = runtime_repo.add_ingestion_job(IngestionJob(source_version_id=database_version.id, status="failed"))
    session.commit()
    stale_job = database_job.model_copy(update={"source_version_id": stale_version.id, "status": "failed"})

    main_app.store.reset()
    try:
        main_app.store.ingestion_jobs[database_job.id] = stale_job

        result = retry_ingestion_job(database_job.id, None, session)

        assert result["job"].source_version_id == database_version.id
        assert result["job"].status == "completed"
        assert result["chunks"][0].source_version_id == database_version.id
        assert result["chunks"][0].content == "Database retry content."
        assert main_app.store.ingestion_jobs[database_job.id].source_version_id == database_version.id
        assert RuntimeRepository(session).get_ingestion_job(database_job.id).source_version_id == database_version.id
    finally:
        main_app.store.reset()


def test_store_audit_log_mirrors_to_database_when_available(monkeypatch):
    import app.db.session as db_session

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine, tables=[Base.metadata.tables["audit_logs"]])
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(db_session, "SessionLocal", session_factory)
    local_store = InMemoryStore()

    audit = local_store.add_audit_log(
        "source_updated",
        "Source",
        "source-1",
        user_id="admin-1",
        after_json={"status": "active"},
    )

    session = session_factory()
    try:
        mirrored = RuntimeRepository(session).list_audit_logs()[0]
    finally:
        session.close()
    assert mirrored.id == audit.id
    assert mirrored.after_json == {"status": "active"}


def test_runtime_job_api_helpers_use_database_when_available():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_subset = [
        Base.metadata.tables["products"],
        Base.metadata.tables["sources"],
        Base.metadata.tables["source_versions"],
        Base.metadata.tables["ingestion_jobs"],
    ]
    Base.metadata.create_all(bind=engine, tables=create_subset)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    catalog_repo = CatalogRepository(session)

    product = catalog_repo.add_product(Product(name="FlyingRC F4", slug="flyingrc-f4", description="Flight controller"))
    source = catalog_repo.add_source(Source(product_id=product.id, title="Manual", source_type=SourceType.markdown))
    version = catalog_repo.add_source_version(SourceVersion(source_id=source.id, version_label="v1", content_hash="9" * 64))
    job = IngestionJob(source_version_id=version.id)
    save_runtime_job(session, job)
    session.expire_all()

    assert list_runtime_jobs(session)[0].id == job.id
    assert get_runtime_job(session, job.id).source_version_id == version.id


def test_provider_config_api_helpers_use_database_when_available():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine, tables=[Base.metadata.tables["provider_configs"]])
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    config = ProviderConfig(provider_type="llm", provider_name="fake", model_name="fake-citation-llm")

    save_provider_config_to_database(session, config)
    session.expire_all()

    assert list_provider_configs_from_database(session)[0].id == config.id
    assert get_provider_config_from_database(session, config.id).model_name == "fake-citation-llm"
    assert delete_provider_config_from_database(session, config.id).id == config.id
    assert list_provider_configs_from_database(session) == []


def test_empty_database_list_table_does_not_fallback_to_stale_memory_store():
    import app.main as main_app

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine, tables=[Base.metadata.tables["provider_configs"]])
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    main_app.store.reset()
    main_app.store.add_provider_config(
        ProviderConfig(provider_type="llm", provider_name="fake", model_name="stale-memory-provider")
    )

    assert main_app.get_provider_configs(session=session) == []
    assert main_app.providers(session=session)["configs"] == []


def test_provider_config_hydration_populates_runtime_store_from_database():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine, tables=[Base.metadata.tables["provider_configs"]])
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    runtime_store = InMemoryStore()
    config = ProviderConfig(provider_type="llm", provider_name="fake", model_name="fake-citation-llm")

    save_provider_config_to_database(session, config)
    session.expire_all()

    assert runtime_store.active_provider_config("llm") is None
    hydrated = hydrate_provider_configs(runtime_store, session)
    assert hydrated[0].id == config.id
    assert runtime_store.active_provider_config("llm").model_name == "fake-citation-llm"


def test_support_import_api_helpers_use_database_when_available():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_subset = [
        Base.metadata.tables["products"],
        Base.metadata.tables["sources"],
        Base.metadata.tables["tickets"],
        Base.metadata.tables["log_sources"],
        Base.metadata.tables["image_assets"],
        Base.metadata.tables["ocr_results"],
    ]
    Base.metadata.create_all(bind=engine, tables=create_subset)
    session = sessionmaker(bind=engine, expire_on_commit=False)()

    product = Product(name="FlyingRC F4", slug="flyingrc-f4", description="Flight controller")
    source = Source(product_id=product.id, title="Support import", source_type=SourceType.ticket_export)
    ticket = Ticket(product_id=product.id, external_id="T-1", title="USB", body="Customer asks.", source_id=source.id)
    log_source = LogSource(product_id=product.id, log_type="boot", content="BOOT OK", source_id=source.id)
    image_asset = ImageAsset(product_id=product.id, storage_uri="local://image.png", image_type="screenshot", source_id=source.id)
    ocr = OcrResult(image_asset_id=image_asset.id, provider_name="fake", model_name="fake-ocr", ocr_text="USB")

    save_product_to_database(session, product)
    save_source_to_database(session, source)
    save_ticket_to_database(session, ticket)
    save_log_source_to_database(session, log_source)
    save_image_asset_to_database(session, image_asset)
    save_ocr_result_to_database(session, ocr)
    session.expire_all()

    assert list_tickets_from_database(session)[0].id == ticket.id
    assert list_log_sources_from_database(session)[0].content == "BOOT OK"
    assert list_image_assets_from_database(session)[0].id == image_asset.id
    assert get_image_asset_from_database(session, image_asset.id).storage_uri == "local://image.png"
    saved_ocr = list_ocr_results_from_database(session, image_asset.id)[0]
    assert saved_ocr.id == ocr.id
    assert saved_ocr.status == "completed"


def test_review_item_helper_hydrates_database_item_for_service():
    import app.main as main_app
    from app.review.service import approve_review_item

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    review_item = ReviewItem(source_type="user_feedback")

    save_review_item_to_database(session, review_item)
    main_app.store.review_items.pop(review_item.id, None)

    hydrated = hydrate_review_item_for_service(session, review_item.id)
    approved = approve_review_item(main_app.store, review_item.id, FailureCategory.insufficient_evidence, reviewer_id="reviewer-3")

    assert hydrated.id == review_item.id
    assert approved.status == ReviewStatus.approved
    assert approved.reviewer_id == "reviewer-3"


def test_review_item_helper_prefers_database_state_over_stale_memory():
    import app.main as main_app

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    database_item = ReviewItem(
        source_type="user_feedback",
        status=ReviewStatus.needs_source_update,
        reviewer_notes="database state",
        failure_category=FailureCategory.bad_parse,
    )
    stale_item = database_item.model_copy(
        update={
            "status": ReviewStatus.open,
            "reviewer_notes": "stale memory",
            "failure_category": None,
        }
    )

    save_review_item_to_database(session, database_item)
    main_app.store.review_items[database_item.id] = stale_item
    try:
        hydrated = hydrate_review_item_for_service(session, database_item.id)

        assert hydrated.status == ReviewStatus.needs_source_update
        assert hydrated.reviewer_notes == "database state"
        assert hydrated.failure_category == FailureCategory.bad_parse
        assert main_app.store.review_items[database_item.id].reviewer_notes == "database state"
    finally:
        main_app.store.reset()


def test_answer_feedback_prefers_database_answer_over_stale_memory():
    import app.main as main_app

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Base.metadata.tables["questions"],
            Base.metadata.tables["retrieval_runs"],
            Base.metadata.tables["answers"],
            Base.metadata.tables["review_items"],
        ],
    )
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    retrieval_repo = RetrievalRepository(session)
    question = retrieval_repo.add_question(Question(raw_text="Can USB power servos?", normalized_text="usb servos"))
    run = retrieval_repo.add_retrieval_run(RetrievalRun(question_id=question.id, normalized_query=question.normalized_text))
    answer = retrieval_repo.add_answer(
        Answer(
            question_id=question.id,
            retrieval_run_id=run.id,
            answer_text="Use external BEC power for servos.",
            evidence_sufficiency=EvidenceSufficiency.sufficient,
            confidence=0.9,
        )
    )
    session.commit()

    stale_question = Question(raw_text="Stale question", normalized_text="stale")
    stale_run = RetrievalRun(question_id=stale_question.id, normalized_query=stale_question.normalized_text)
    stale_answer = answer.model_copy(update={"question_id": stale_question.id, "retrieval_run_id": stale_run.id})
    main_app.store.reset()
    try:
        main_app.store.answers[answer.id] = stale_answer

        item = post_feedback(answer.id, AnswerFeedbackCreate(feedback_type="incorrect", notes="wrong"), None, session)

        assert item.answer_id == answer.id
        assert item.question_id == question.id
        assert list_review_items_from_database(session)[0].question_id == question.id
        assert main_app.store.answers[answer.id].question_id == question.id
    finally:
        main_app.store.reset()


def test_eval_result_to_review_prefers_database_result_over_stale_memory():
    import app.main as main_app

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    review_repo = ReviewEvalRepository(session)
    eval_run = review_repo.add_eval_run(EvalRun(name="MVP eval"))
    eval_case = review_repo.add_eval_case(EvalCase(question_text="Can USB power servos?"))
    database_result = review_repo.add_eval_result(
        EvalResult(
            eval_run_id=eval_run.id,
            eval_case_id=eval_case.id,
            question_id=uuid4(),
            retrieval_run_id=uuid4(),
            answer_id=uuid4(),
            recall_at_20=0.0,
            rerank_at_5=0.0,
            citation_support_rate=0.0,
            unsupported_claim_rate=1.0,
            need_review=True,
            failure_category=FailureCategory.unsupported_claim,
        )
    )
    session.commit()
    stale_result = database_result.model_copy(
        update={
            "question_id": uuid4(),
            "answer_id": uuid4(),
            "failure_category": FailureCategory.insufficient_evidence,
        }
    )

    main_app.store.reset()
    try:
        main_app.store.eval_results[database_result.id] = stale_result

        item = eval_result_to_review(database_result.id, None, session)

        assert item.eval_result_id == database_result.id
        assert item.question_id == database_result.question_id
        assert item.answer_id == database_result.answer_id
        assert item.failure_category == FailureCategory.unsupported_claim
        assert list_review_items_from_database(session)[0].question_id == database_result.question_id
        assert main_app.store.eval_results[database_result.id].question_id == database_result.question_id
    finally:
        main_app.store.reset()


def test_eval_run_compare_prefers_database_runs_over_stale_memory():
    import app.main as main_app

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine, tables=[Base.metadata.tables["eval_runs"]])
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    review_repo = ReviewEvalRepository(session)
    baseline = review_repo.add_eval_run(EvalRun(name="baseline", summary_metrics_json={"recall_at_20": 0.2, "case_count": 10}))
    candidate = review_repo.add_eval_run(EvalRun(name="candidate", summary_metrics_json={"recall_at_20": 0.7, "case_count": 10}))
    session.commit()

    main_app.store.reset()
    try:
        main_app.store.eval_runs[baseline.id] = baseline.model_copy(update={"summary_metrics_json": {"recall_at_20": 0.9, "case_count": 10}})
        main_app.store.eval_runs[candidate.id] = candidate.model_copy(update={"summary_metrics_json": {"recall_at_20": 0.1, "case_count": 10}})

        comparison = compare_eval_runs(baseline.id, candidate.id, session)

        assert comparison["baseline"].summary_metrics_json["recall_at_20"] == 0.2
        assert comparison["candidate"].summary_metrics_json["recall_at_20"] == 0.7
        assert comparison["deltas"]["recall_at_20"] == pytest.approx(0.5)
        assert main_app.store.eval_runs[baseline.id].summary_metrics_json["recall_at_20"] == 0.2
    finally:
        main_app.store.reset()


def test_eval_case_patch_prefers_database_case_over_stale_memory():
    import app.main as main_app

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine, tables=[Base.metadata.tables["eval_cases"]])
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    review_repo = ReviewEvalRepository(session)
    database_case = review_repo.add_eval_case(
        EvalCase(question_text="Database question", tags_json=["db"], difficulty="normal")
    )
    session.commit()
    stale_case = database_case.model_copy(update={"question_text": "Stale question", "tags_json": ["stale"], "difficulty": "easy"})

    main_app.store.reset()
    try:
        main_app.store.eval_cases[database_case.id] = stale_case

        patched = patch_eval_case(database_case.id, EvalCasePatch(difficulty="hard"), CurrentUser(user_id="eval-admin", role="admin"), session)

        assert patched.question_text == "Database question"
        assert patched.tags_json == ["db"]
        assert patched.difficulty == "hard"
        assert get_eval_case_from_database(session, database_case.id).question_text == "Database question"
        assert main_app.store.eval_cases[database_case.id].question_text == "Database question"
    finally:
        main_app.store.reset()


def test_review_conversion_helpers_use_database_context_and_persist_outputs():
    import app.main as main_app
    from app.review.service import review_to_eval_case, review_to_faq

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()

    product = Product(name="FlyingRC F4", slug="flyingrc-f4", description="Flight controller")
    source = Source(product_id=product.id, title="Manual", source_type=SourceType.markdown)
    version = SourceVersion(source_id=source.id, version_label="v1", content_hash="7" * 64)
    artifact = SourceArtifact(source_version_id=version.id, storage_uri="memory://manual", content="USB is configuration only.")
    chunk = Chunk(
        source_version_id=version.id,
        product_id=product.id,
        chunk_index=0,
        content=artifact.content,
        content_hash="6" * 64,
        token_count=4,
    )
    question = Question(product_id=product.id, raw_text="Can USB power servos?", normalized_text="usb servos")
    retrieval_run = RetrievalRun(question_id=question.id, normalized_query=question.normalized_text)
    candidate = RetrievalCandidate(retrieval_run_id=retrieval_run.id, chunk_id=chunk.id, stage="reranked", source="fake", rank=1)
    evidence = Evidence(retrieval_run_id=retrieval_run.id, chunk_id=chunk.id, rank=1, score=1.0, quote=chunk.content, selection_reason="top")
    answer = Answer(
        question_id=question.id,
        retrieval_run_id=retrieval_run.id,
        answer_text="USB is for configuration only.",
        citation_map_json={"usb": [evidence.id]},
        evidence_sufficiency=EvidenceSufficiency.sufficient,
        confidence=0.9,
    )
    review_item = ReviewItem(
        source_type="user_feedback",
        question_id=question.id,
        answer_id=answer.id,
        edited_answer_text="USB is for configuration only. Do not power servos from USB.",
    )

    save_product_to_database(session, product)
    save_source_to_database(session, source)
    save_source_version_bundle_to_database(session, version, artifact, [chunk])
    save_ask_response_to_database(session, question, retrieval_run, [candidate], [evidence], answer, review_item)
    main_app.store.reset()
    try:
        hydrated = hydrate_review_context_for_service(session, review_item.id)
        eval_case = review_to_eval_case(main_app.store, review_item.id)
        faq, faq_source, faq_version, faq_artifact, faq_chunks = review_to_faq(main_app.store, review_item.id)
        save_eval_case_to_database(session, eval_case)
        save_source_to_database(session, faq_source)
        save_source_version_bundle_to_database(session, faq_version, faq_artifact, faq_chunks)
        save_approved_faq_to_database(session, faq)
        session.expire_all()

        assert hydrated.id == review_item.id
        assert get_chunk_from_database(session, chunk.id).id == chunk.id
        assert get_eval_case_from_database(session, eval_case.id).expected_chunk_ids_json == [chunk.id]
        assert get_approved_faq_from_database(session, faq.id).answer_text.startswith("USB is for configuration")
        assert list_chunks_from_database(session, faq_version.id)
    finally:
        main_app.store.reset()


def test_catalog_api_helpers_use_database_when_available():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_subset = [
        Base.metadata.tables["products"],
        Base.metadata.tables["product_aliases"],
        Base.metadata.tables["sources"],
    ]
    Base.metadata.create_all(bind=engine, tables=create_subset)
    session = sessionmaker(bind=engine, expire_on_commit=False)()

    product = Product(name="FlyingRC F4", slug="flyingrc-f4", description="Flight controller")
    save_product_to_database(session, product)
    alias = ProductAlias(product_id=product.id, alias="F4 FC", confidence=0.95)
    save_alias_to_database(session, alias)
    source = Source(product_id=product.id, title="Manual", source_type=SourceType.markdown, trust_level="official")
    save_source_to_database(session, source)
    session.expire_all()

    assert list_products_from_database(session)[0].id == product.id
    assert get_product_from_database(session, product.id).slug == "flyingrc-f4"
    assert list_aliases_from_database(session, product.id)[0].id == alias.id
    assert list_sources_from_database(session)[0].id == source.id
    assert get_source_from_database(session, source.id).title == "Manual"


def test_source_version_api_helpers_use_database_when_available():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_subset = [
        Base.metadata.tables["products"],
        Base.metadata.tables["sources"],
        Base.metadata.tables["source_versions"],
        Base.metadata.tables["source_artifacts"],
        Base.metadata.tables["chunks"],
        Base.metadata.tables["chunk_embeddings"],
    ]
    Base.metadata.create_all(bind=engine, tables=create_subset)
    session = sessionmaker(bind=engine, expire_on_commit=False)()

    product = Product(name="FlyingRC F4", slug="flyingrc-f4", description="Flight controller")
    source = Source(product_id=product.id, title="Manual", source_type=SourceType.markdown, trust_level="official")
    version = SourceVersion(source_id=source.id, version_label="v1", content_hash="8" * 64, error_message="bad parse")
    artifact = SourceArtifact(source_version_id=version.id, storage_uri="memory://manual", content="USB is configuration only.")
    chunk = Chunk(
        source_version_id=version.id,
        product_id=product.id,
        chunk_index=0,
        content=artifact.content,
        content_hash="7" * 64,
        token_count=4,
    )

    save_product_to_database(session, product)
    save_source_to_database(session, source)
    save_source_version_bundle_to_database(session, version, artifact, [chunk])
    embedding = ChunkEmbedding(chunk_id=chunk.id, provider_name="fake", model_name="fake-hash-embedding", embedding_dimension=3, vector=[0.1, 0.2, 0.3])
    save_chunk_embeddings_to_database(session, [embedding])
    version.status = "disabled"
    chunk.enabled = False
    save_source_version_to_database(session, version)
    save_chunks_to_database(session, [chunk])
    session.expire_all()

    assert list_source_versions_from_database(session, source.id)[0].status == "disabled"
    assert get_source_version_from_database(session, version.id).error_message == "bad parse"
    assert get_artifact_from_database(session, artifact.id).id == artifact.id
    assert list_artifacts_from_database(session, version.id)[0].content == artifact.content
    assert list_chunks_from_database(session, version.id)[0].enabled is False
    assert list_chunk_embeddings_from_database(session, chunk.id)[0].id == embedding.id


def test_retrieval_catalog_hydration_loads_database_chunks_for_ask_pipeline():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_subset = [
        Base.metadata.tables["products"],
        Base.metadata.tables["product_aliases"],
        Base.metadata.tables["sources"],
        Base.metadata.tables["source_versions"],
        Base.metadata.tables["chunks"],
        Base.metadata.tables["chunk_embeddings"],
    ]
    Base.metadata.create_all(bind=engine, tables=create_subset)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    catalog = CatalogRepository(session)
    product = catalog.add_product(Product(name="FlyingRC F4", slug="flyingrc-f4", description="Flight controller"))
    catalog.add_alias(ProductAlias(product_id=product.id, alias="F4", confidence=0.9))
    source = catalog.add_source(Source(product_id=product.id, title="Manual", source_type=SourceType.markdown))
    version = catalog.add_source_version(SourceVersion(source_id=source.id, version_label="v1", content_hash="0" * 64))
    chunk = catalog.add_chunks(
        [
            Chunk(
                source_version_id=version.id,
                product_id=product.id,
                chunk_index=0,
                content="USB power is for configuration. Do not power servos from USB.",
                content_hash="1" * 64,
                token_count=11,
            )
        ]
    )[0]
    session.commit()
    session.expire_all()
    runtime_store = InMemoryStore()

    counts = hydrate_retrieval_catalog(runtime_store, session, product.id)
    assert counts["chunks"] == 1
    assert runtime_store.aliases_for_product(product.id)[0].alias == "F4"
    question = runtime_store.add_question(
        Question(product_id=product.id, raw_text="Can USB power servos?", normalized_text="usb power servos")
    )
    _run, candidates, evidence = run_retrieval(runtime_store, question)
    assert any(candidate.chunk_id == chunk.id for candidate in candidates)
    assert evidence[0].chunk_id == chunk.id


def test_ingestion_job_can_hydrate_source_version_from_database_and_persist_outputs():
    import app.main as main_app
    from app.ingestion.jobs import run_ingestion_job

    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_subset = [
        Base.metadata.tables["products"],
        Base.metadata.tables["sources"],
        Base.metadata.tables["source_versions"],
        Base.metadata.tables["source_artifacts"],
        Base.metadata.tables["chunks"],
    ]
    Base.metadata.create_all(bind=engine, tables=create_subset)
    session = sessionmaker(bind=engine, expire_on_commit=False)()

    product = Product(name="FlyingRC F4", slug="flyingrc-f4", description="Flight controller")
    source = Source(product_id=product.id, title="Manual", source_type=SourceType.markdown, trust_level="official")
    version = SourceVersion(source_id=source.id, version_label="v1", content_hash="a" * 64)
    artifact = SourceArtifact(source_version_id=version.id, storage_uri="memory://manual", content="USB is configuration only.")

    save_product_to_database(session, product)
    save_source_to_database(session, source)
    save_source_version_bundle_to_database(session, version, artifact, [])
    main_app.store.reset()
    try:
        hydrated = hydrate_source_version_for_service(session, version.id)
        job, chunks = run_ingestion_job(version.id)
        save_source_version_to_database(session, main_app.store.source_versions[version.id])
        save_chunks_to_database(session, chunks)
        session.expire_all()

        assert hydrated.id == version.id
        assert artifact.id in main_app.store.source_artifacts
        assert job.status == "completed"
        assert get_source_version_from_database(session, version.id).status == "ingested"
        assert list_chunks_from_database(session, version.id)
    finally:
        main_app.store.reset()


def test_source_version_hydration_tracks_existing_chunk_hashes():
    import app.main as main_app
    from app.ingestion.chunking import content_hash
    from app.ingestion.jobs import run_ingestion_job

    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_subset = [
        Base.metadata.tables["products"],
        Base.metadata.tables["sources"],
        Base.metadata.tables["source_versions"],
        Base.metadata.tables["source_artifacts"],
        Base.metadata.tables["chunks"],
    ]
    Base.metadata.create_all(bind=engine, tables=create_subset)
    session = sessionmaker(bind=engine, expire_on_commit=False)()

    product = Product(name="FlyingRC F4", slug="flyingrc-f4", description="Flight controller")
    source = Source(product_id=product.id, title="Manual", source_type=SourceType.markdown, trust_level="official")
    version = SourceVersion(source_id=source.id, version_label="v1", content_hash="b" * 64)
    artifact = SourceArtifact(source_version_id=version.id, storage_uri="memory://manual", content="USB is configuration only.")
    chunk = Chunk(
        source_version_id=version.id,
        product_id=product.id,
        chunk_index=0,
        content=artifact.content,
        content_hash=content_hash(artifact.content),
        token_count=4,
    )

    save_product_to_database(session, product)
    save_source_to_database(session, source)
    save_source_version_bundle_to_database(session, version, artifact, [chunk])
    main_app.store.reset()
    try:
        hydrated = hydrate_source_version_for_service(session, version.id)
        job, chunks = run_ingestion_job(version.id)

        assert hydrated.id == version.id
        assert chunk.id in main_app.store.chunks
        assert chunk.content_hash in main_app.store.chunk_hashes_by_version[version.id]
        assert job.status == "completed"
        assert chunks == []
    finally:
        main_app.store.reset()


def test_ingestion_worker_processes_database_backed_queue_message(monkeypatch):
    import app.main as main_app
    import app.workers.ingestion_worker as worker
    from app.ingestion.queue import encode_ingestion_job

    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_subset = [
        Base.metadata.tables["products"],
        Base.metadata.tables["sources"],
        Base.metadata.tables["source_versions"],
        Base.metadata.tables["source_artifacts"],
        Base.metadata.tables["chunks"],
        Base.metadata.tables["chunk_embeddings"],
        Base.metadata.tables["ingestion_jobs"],
    ]
    Base.metadata.create_all(bind=engine, tables=create_subset)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(worker, "SessionLocal", session_factory)
    session = session_factory()
    catalog_repo = CatalogRepository(session)
    runtime_repo = RuntimeRepository(session)

    product = catalog_repo.add_product(Product(name="FlyingRC F4", slug="flyingrc-f4", description="Flight controller"))
    source = catalog_repo.add_source(Source(product_id=product.id, title="Manual", source_type=SourceType.markdown, trust_level="official"))
    version = catalog_repo.add_source_version(SourceVersion(source_id=source.id, version_label="v1", content_hash="b" * 64))
    catalog_repo.add_artifact(SourceArtifact(source_version_id=version.id, storage_uri="memory://manual", content="USB is configuration only."))
    job = runtime_repo.add_ingestion_job(IngestionJob(source_version_id=version.id))
    session.commit()
    session.close()

    main_app.store.reset()
    try:
        worker.process_message(encode_ingestion_job(version.id, job.id))

        session = session_factory()
        try:
            completed = RuntimeRepository(session).get_ingestion_job(job.id)
            chunks = CatalogRepository(session).chunks_for_version(version.id)
            embeddings = CatalogRepository(session).embeddings_for_chunk(chunks[0].id)
        finally:
            session.close()
        assert completed.status == "completed"
        assert completed.chunk_count == 1
        assert chunks[0].content == "USB is configuration only."
        assert embeddings[0].chunk_id == chunks[0].id
    finally:
        main_app.store.reset()


def test_ingestion_worker_failed_job_creates_source_issue_review_item(monkeypatch):
    import app.main as main_app
    import app.workers.ingestion_worker as worker
    from app.ingestion.queue import encode_ingestion_job

    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_subset = [
        Base.metadata.tables["products"],
        Base.metadata.tables["sources"],
        Base.metadata.tables["source_versions"],
        Base.metadata.tables["source_artifacts"],
        Base.metadata.tables["chunks"],
        Base.metadata.tables["chunk_embeddings"],
        Base.metadata.tables["ingestion_jobs"],
        Base.metadata.tables["provider_configs"],
        Base.metadata.tables["review_items"],
    ]
    Base.metadata.create_all(bind=engine, tables=create_subset)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(worker, "SessionLocal", session_factory)
    session = session_factory()
    catalog_repo = CatalogRepository(session)
    runtime_repo = RuntimeRepository(session)
    review_repo = ReviewEvalRepository(session)

    product = catalog_repo.add_product(Product(name="FlyingRC F4", slug="flyingrc-f4", description="Flight controller"))
    source = catalog_repo.add_source(Source(product_id=product.id, title="Manual", source_type=SourceType.markdown, trust_level="official"))
    version = catalog_repo.add_source_version(SourceVersion(source_id=source.id, version_label="v1", content_hash="b" * 64))
    catalog_repo.add_artifact(SourceArtifact(source_version_id=version.id, storage_uri="memory://manual", content="USB is configuration only."))
    review_repo.add_provider_config(
        ProviderConfig(provider_type="embedding", provider_name="openai", model_name="text-embedding-example")
    )
    job = runtime_repo.add_ingestion_job(IngestionJob(source_version_id=version.id))
    session.commit()
    session.close()

    main_app.store.reset()
    try:
        worker.process_message(encode_ingestion_job(version.id, job.id))

        session = session_factory()
        try:
            failed = RuntimeRepository(session).get_ingestion_job(job.id)
            failed_version = CatalogRepository(session).get_source_version(version.id)
            chunks = CatalogRepository(session).chunks_for_version(version.id)
            review_items = ReviewEvalRepository(session).list_review_items()
        finally:
            session.close()
        assert failed.status == "failed"
        assert failed_version.status == "failed"
        assert chunks == []
        assert review_items[0].source_type == "source_issue"
        assert review_items[0].failure_category == FailureCategory.bad_parse
        assert "failed ingestion" in review_items[0].reviewer_notes
    finally:
        main_app.store.reset()


def test_retrieval_repository_round_trips_ask_records_in_sqlite():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_subset = [
        Base.metadata.tables["products"],
        Base.metadata.tables["sources"],
        Base.metadata.tables["source_versions"],
        Base.metadata.tables["source_artifacts"],
        Base.metadata.tables["chunks"],
        Base.metadata.tables["questions"],
        Base.metadata.tables["question_attachments"],
        Base.metadata.tables["retrieval_runs"],
        Base.metadata.tables["retrieval_candidates"],
        Base.metadata.tables["evidences"],
        Base.metadata.tables["model_runs"],
        Base.metadata.tables["answers"],
    ]
    Base.metadata.create_all(bind=engine, tables=create_subset)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    catalog_repo = CatalogRepository(session)
    retrieval_repo = RetrievalRepository(session)

    product = catalog_repo.add_product(Product(name="FlyingRC F4", slug="flyingrc-f4", description="Flight controller"))
    source = catalog_repo.add_source(Source(product_id=product.id, title="Manual", source_type=SourceType.markdown))
    version = catalog_repo.add_source_version(SourceVersion(source_id=source.id, version_label="v1", content_hash="d" * 64))
    artifact = catalog_repo.add_artifact(SourceArtifact(source_version_id=version.id, storage_uri="memory://manual", content="USB only."))
    chunk = catalog_repo.add_chunks(
        [
            Chunk(
                source_version_id=version.id,
                product_id=product.id,
                chunk_index=0,
                content="USB power is for configuration only.",
                content_hash="e" * 64,
                token_count=6,
            )
        ]
    )[0]
    question = retrieval_repo.add_question(
        Question(product_id=product.id, raw_text="Can USB power servos?", normalized_text="can usb power servos")
    )
    attachment = retrieval_repo.add_question_attachment(
        QuestionAttachment(question_id=question.id, artifact_id=artifact.id, attachment_type="file", description="manual excerpt")
    )
    run = retrieval_repo.add_retrieval_run(RetrievalRun(question_id=question.id, normalized_query=question.normalized_text))
    candidate = retrieval_repo.add_candidates(
        [RetrievalCandidate(retrieval_run_id=run.id, chunk_id=chunk.id, stage="reranked", source="hybrid", rank=1, rerank_score=0.9)]
    )[0]
    evidence = retrieval_repo.add_evidence(
        [Evidence(retrieval_run_id=run.id, chunk_id=chunk.id, rank=1, score=0.9, quote=chunk.content, selection_reason="top rerank")]
    )[0]
    model_run = retrieval_repo.add_model_run(
        ModelRun(provider_type="llm", provider_name="fake", model_name="fake-citation-llm", input_hash="f" * 64)
    )
    answer = retrieval_repo.add_answer(
        Answer(
            question_id=question.id,
            retrieval_run_id=run.id,
            answer_text="Do not power servos from USB.",
            citation_map_json={"usb": [evidence.id]},
            evidence_sufficiency=EvidenceSufficiency.sufficient,
            confidence=0.9,
            model_run_id=model_run.id,
        )
    )
    session.commit()
    session.expire_all()

    assert retrieval_repo.attachments_for_question(question.id)[0].id == attachment.id
    assert retrieval_repo.candidates_for_run(run.id)[0].id == candidate.id
    assert retrieval_repo.evidence_for_run(run.id)[0].id == evidence.id
    assert retrieval_repo.get_answer(answer.id).citation_map_json["usb"][0] == evidence.id


def test_database_answer_evidence_endpoint_does_not_fall_back_to_stale_memory():
    import app.main as main_app

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Base.metadata.tables["questions"],
            Base.metadata.tables["retrieval_runs"],
            Base.metadata.tables["evidences"],
            Base.metadata.tables["answers"],
        ],
    )
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    retrieval_repo = RetrievalRepository(session)
    question = retrieval_repo.add_question(Question(raw_text="Can USB power servos?", normalized_text="usb servos"))
    run = retrieval_repo.add_retrieval_run(RetrievalRun(question_id=question.id, normalized_query=question.normalized_text))
    answer = retrieval_repo.add_answer(
        Answer(
            question_id=question.id,
            retrieval_run_id=run.id,
            answer_text="No evidence was selected.",
            evidence_sufficiency=EvidenceSufficiency.insufficient,
            confidence=0.0,
        )
    )
    session.commit()

    main_app.store.reset()
    try:
        main_app.store.add_evidence(
            [Evidence(retrieval_run_id=run.id, chunk_id=question.id, rank=1, score=1.0, quote="stale", selection_reason="stale")]
        )

        assert get_answer_evidence(answer.id, session) == []
    finally:
        main_app.store.reset()


def test_database_review_detail_does_not_fall_back_to_stale_memory_children():
    import app.main as main_app

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Base.metadata.tables["products"],
            Base.metadata.tables["sources"],
            Base.metadata.tables["source_versions"],
            Base.metadata.tables["source_artifacts"],
            Base.metadata.tables["chunks"],
            Base.metadata.tables["questions"],
            Base.metadata.tables["question_attachments"],
            Base.metadata.tables["retrieval_runs"],
            Base.metadata.tables["retrieval_candidates"],
            Base.metadata.tables["evidences"],
            Base.metadata.tables["answers"],
            Base.metadata.tables["review_items"],
        ],
    )
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    retrieval_repo = RetrievalRepository(session)
    review_repo = ReviewEvalRepository(session)
    question = retrieval_repo.add_question(Question(raw_text="Can USB power servos?", normalized_text="usb servos"))
    run = retrieval_repo.add_retrieval_run(RetrievalRun(question_id=question.id, normalized_query=question.normalized_text))
    answer = retrieval_repo.add_answer(
        Answer(
            question_id=question.id,
            retrieval_run_id=run.id,
            answer_text="No evidence was selected.",
            evidence_sufficiency=EvidenceSufficiency.insufficient,
            confidence=0.0,
        )
    )
    item = review_repo.add_review_item(ReviewItem(source_type="low_confidence_answer", question_id=question.id, answer_id=answer.id))
    session.commit()

    main_app.store.reset()
    try:
        main_app.store.add_evidence(
            [Evidence(retrieval_run_id=run.id, chunk_id=question.id, rank=1, score=1.0, quote="stale", selection_reason="stale")]
        )
        main_app.store.add_candidates(
            [RetrievalCandidate(retrieval_run_id=run.id, chunk_id=question.id, stage="reranked", source="stale", rank=1)]
        )
        main_app.store.add_question_attachment(
            QuestionAttachment(question_id=question.id, artifact_id=question.id, attachment_type="file", description="stale")
        )

        detail = get_review_item_detail(item.id, session)
        assert detail.evidence == []
        assert detail.candidates == []
        assert detail.attachments == []
    finally:
        main_app.store.reset()


def test_database_image_ocr_results_do_not_fall_back_to_stale_memory():
    import app.main as main_app

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine, tables=[Base.metadata.tables["image_assets"], Base.metadata.tables["ocr_results"]])
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    image_asset = ReviewEvalRepository(session).add_image_asset(
        ImageAsset(storage_uri="local://image.png", image_type="screenshot")
    )
    session.commit()

    main_app.store.reset()
    try:
        main_app.store.add_ocr_result(
            OcrResult(
                image_asset_id=image_asset.id,
                provider_name="fake",
                model_name="fake-ocr",
                ocr_text="stale text",
            )
        )

        assert get_image_ocr_results(image_asset.id, session) == []
    finally:
        main_app.store.reset()


def test_image_ocr_prefers_database_image_asset_over_stale_memory(monkeypatch):
    import app.main as main_app

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(bind=engine, tables=[Base.metadata.tables["image_assets"], Base.metadata.tables["ocr_results"]])
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    image_asset = ReviewEvalRepository(session).add_image_asset(
        ImageAsset(storage_uri="local://database-image.png", image_type="screenshot")
    )
    session.commit()
    seen_uris = []

    def fake_ocr(_provider_config, image_uri):
        seen_uris.append(image_uri)
        return OCRResult("fake", "fake-ocr", 1, text="OCR from database image", confidence=0.8)

    main_app.store.reset()
    try:
        main_app.store.image_assets[image_asset.id] = image_asset.model_copy(update={"storage_uri": "local://stale-image.png"})
        monkeypatch.setattr(main_app, "run_configured_ocr", fake_ocr)

        result = post_image_ocr(image_asset.id, OcrResultCreate(), None, session)

        assert seen_uris == ["local://database-image.png"]
        assert result["ocr_result"].ocr_text == "OCR from database image"
        assert list_ocr_results_from_database(session, image_asset.id)[0].ocr_text == "OCR from database image"
        assert main_app.store.image_assets[image_asset.id].storage_uri == "local://database-image.png"
    finally:
        main_app.store.reset()


def test_ask_api_helpers_mirror_records_to_database_when_available():
    import app.main as main_app

    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_subset = [
        Base.metadata.tables["products"],
        Base.metadata.tables["sources"],
        Base.metadata.tables["source_versions"],
        Base.metadata.tables["source_artifacts"],
        Base.metadata.tables["chunks"],
        Base.metadata.tables["questions"],
        Base.metadata.tables["question_attachments"],
        Base.metadata.tables["retrieval_runs"],
        Base.metadata.tables["retrieval_candidates"],
        Base.metadata.tables["evidences"],
        Base.metadata.tables["model_runs"],
        Base.metadata.tables["answers"],
        Base.metadata.tables["eval_cases"],
        Base.metadata.tables["eval_runs"],
        Base.metadata.tables["eval_results"],
        Base.metadata.tables["review_items"],
    ]
    Base.metadata.create_all(bind=engine, tables=create_subset)
    session = sessionmaker(bind=engine, expire_on_commit=False)()

    product = Product(name="FlyingRC F4", slug="flyingrc-f4", description="Flight controller")
    source = Source(product_id=product.id, title="Manual", source_type=SourceType.markdown)
    version = SourceVersion(source_id=source.id, version_label="v1", content_hash="6" * 64)
    artifact = SourceArtifact(source_version_id=version.id, storage_uri="memory://manual", content="USB is configuration only.")
    chunk = Chunk(
        source_version_id=version.id,
        product_id=product.id,
        chunk_index=0,
        content=artifact.content,
        content_hash="5" * 64,
        token_count=4,
    )
    question = Question(product_id=product.id, raw_text="Can USB power servos?", normalized_text="usb servos")
    retrieval_run = RetrievalRun(question_id=question.id, normalized_query=question.normalized_text)
    candidate = RetrievalCandidate(retrieval_run_id=retrieval_run.id, chunk_id=chunk.id, stage="reranked", source="fake", rank=1)
    evidence = Evidence(retrieval_run_id=retrieval_run.id, chunk_id=chunk.id, rank=1, score=1.0, quote=chunk.content, selection_reason="top")
    model_run = ModelRun(provider_type="llm", provider_name="fake", model_name="fake-citation-llm", input_hash="4" * 64)
    answer = Answer(
        question_id=question.id,
        retrieval_run_id=retrieval_run.id,
        answer_text="USB is for configuration only.",
        citation_map_json={"usb": [evidence.id]},
        evidence_sufficiency=EvidenceSufficiency.sufficient,
        confidence=0.9,
        model_run_id=model_run.id,
    )
    review_item = ReviewItem(source_type="user_feedback", question_id=question.id, answer_id=answer.id)
    attachment = QuestionAttachment(question_id=question.id, artifact_id=artifact.id, attachment_type="file", description="manual")
    eval_case = EvalCase(product_id=product.id, question_text=question.raw_text, expected_chunk_ids_json=[chunk.id])
    eval_run = EvalRun(name="MVP eval", summary_metrics_json={"case_count": 1})
    eval_result = EvalResult(
        eval_run_id=eval_run.id,
        eval_case_id=eval_case.id,
        question_id=question.id,
        retrieval_run_id=retrieval_run.id,
        answer_id=answer.id,
        recall_at_20=1.0,
        rerank_at_5=1.0,
        citation_support_rate=1.0,
        unsupported_claim_rate=0.0,
        need_review=False,
    )

    save_product_to_database(session, product)
    save_source_to_database(session, source)
    save_source_version_bundle_to_database(session, version, artifact, [chunk])
    main_app.store.model_runs[model_run.id] = model_run
    try:
        save_ask_response_to_database(session, question, retrieval_run, [candidate], [evidence], answer, review_item)
        save_question_attachment_to_database(session, attachment)
        session.expire_all()

        assert get_question_from_database(session, question.id).id == question.id
        assert get_retrieval_run_from_database(session, retrieval_run.id).id == retrieval_run.id
        assert list_retrieval_candidates_from_database(session, retrieval_run.id)[0].id == candidate.id
        assert list_evidence_from_database(session, retrieval_run.id)[0].id == evidence.id
        assert get_model_run_from_database(session, model_run.id).id == model_run.id
        assert get_answer_from_database(session, answer.id).citation_map_json["usb"][0] == evidence.id
        assert list_question_attachments_from_database(session, question.id)[0].id == attachment.id
        save_eval_case_to_database(session, eval_case)
        save_eval_run_results_to_database(session, eval_run, [eval_result])
        session.expire_all()
        assert list_eval_cases_from_database(session)[0].id == eval_case.id
        assert get_eval_case_from_database(session, eval_case.id).question_text == question.raw_text
        assert list_eval_runs_from_database(session)[0].id == eval_run.id
        assert get_eval_run_from_database(session, eval_run.id).summary_metrics_json["case_count"] == 1
        assert list_eval_results_from_database(session, eval_run.id)[0].id == eval_result.id
        assert get_eval_result_from_database(session, eval_result.id).citation_support_rate == 1.0
        review_item.reviewer_notes = "checked by reviewer"
        review_item.failure_category = FailureCategory.insufficient_evidence
        save_review_item_to_database(session, review_item)
        session.expire_all()
        assert list_review_items_from_database(session)[0].id == review_item.id
        assert get_review_item_from_database(session, review_item.id).reviewer_notes == "checked by reviewer"
    finally:
        main_app.store.model_runs.pop(model_run.id, None)


def test_review_context_hydration_restores_eval_result_from_database():
    import app.main as main_app

    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_subset = [
        Base.metadata.tables["products"],
        Base.metadata.tables["sources"],
        Base.metadata.tables["source_versions"],
        Base.metadata.tables["source_artifacts"],
        Base.metadata.tables["chunks"],
        Base.metadata.tables["questions"],
        Base.metadata.tables["retrieval_runs"],
        Base.metadata.tables["retrieval_candidates"],
        Base.metadata.tables["evidences"],
        Base.metadata.tables["model_runs"],
        Base.metadata.tables["answers"],
        Base.metadata.tables["eval_cases"],
        Base.metadata.tables["eval_runs"],
        Base.metadata.tables["eval_results"],
        Base.metadata.tables["review_items"],
    ]
    Base.metadata.create_all(bind=engine, tables=create_subset)
    session = sessionmaker(bind=engine, expire_on_commit=False)()

    product = Product(name="FlyingRC F4", slug="flyingrc-f4", description="Flight controller")
    source = Source(product_id=product.id, title="Manual", source_type=SourceType.markdown)
    version = SourceVersion(source_id=source.id, version_label="v1", content_hash="6" * 64)
    artifact = SourceArtifact(source_version_id=version.id, storage_uri="memory://manual", content="USB is configuration only.")
    chunk = Chunk(
        source_version_id=version.id,
        product_id=product.id,
        chunk_index=0,
        content=artifact.content,
        content_hash="5" * 64,
        token_count=4,
    )
    question = Question(product_id=product.id, raw_text="Can USB power servos?", normalized_text="usb servos")
    retrieval_run = RetrievalRun(question_id=question.id, normalized_query=question.normalized_text)
    candidate = RetrievalCandidate(retrieval_run_id=retrieval_run.id, chunk_id=chunk.id, stage="reranked", source="fake", rank=1)
    evidence = Evidence(retrieval_run_id=retrieval_run.id, chunk_id=chunk.id, rank=1, score=1.0, quote=chunk.content, selection_reason="top")
    model_run = ModelRun(provider_type="llm", provider_name="fake", model_name="fake-citation-llm", input_hash="4" * 64)
    answer = Answer(
        question_id=question.id,
        retrieval_run_id=retrieval_run.id,
        answer_text="USB is for configuration only.",
        citation_map_json={"usb": [evidence.id]},
        evidence_sufficiency=EvidenceSufficiency.sufficient,
        confidence=0.9,
        model_run_id=model_run.id,
    )
    eval_case = EvalCase(product_id=product.id, question_text=question.raw_text, expected_chunk_ids_json=[chunk.id])
    eval_run = EvalRun(name="MVP eval", summary_metrics_json={"case_count": 1})
    eval_result = EvalResult(
        eval_run_id=eval_run.id,
        eval_case_id=eval_case.id,
        question_id=question.id,
        retrieval_run_id=retrieval_run.id,
        answer_id=answer.id,
        recall_at_20=1.0,
        rerank_at_5=1.0,
        citation_support_rate=1.0,
        unsupported_claim_rate=0.0,
        need_review=True,
        failure_category=FailureCategory.insufficient_evidence,
    )
    review_item = ReviewItem(
        source_type="eval_failure",
        question_id=question.id,
        answer_id=answer.id,
        eval_result_id=eval_result.id,
        failure_category=FailureCategory.insufficient_evidence,
    )

    save_product_to_database(session, product)
    save_source_to_database(session, source)
    save_source_version_bundle_to_database(session, version, artifact, [chunk])
    main_app.store.model_runs[model_run.id] = model_run
    try:
        save_ask_response_to_database(session, question, retrieval_run, [candidate], [evidence], answer, None)
        save_eval_case_to_database(session, eval_case)
        save_eval_run_results_to_database(session, eval_run, [eval_result])
        save_review_item_to_database(session, review_item)
        session.expire_all()
        main_app.store.reset()

        hydrated = hydrate_review_context_for_service(session, review_item.id)
        assert hydrated.id == review_item.id
        assert main_app.store.eval_results[eval_result.id].failure_category == FailureCategory.insufficient_evidence
        assert main_app.store.questions[question.id].raw_text == question.raw_text
        assert main_app.store.answers[answer.id].answer_text == answer.answer_text
        assert main_app.store.retrieval_runs[retrieval_run.id].id == retrieval_run.id
    finally:
        main_app.store.reset()


def test_review_eval_repository_round_trips_remaining_mvp_records_in_sqlite():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_subset = [
        Base.metadata.tables["products"],
        Base.metadata.tables["sources"],
        Base.metadata.tables["source_versions"],
        Base.metadata.tables["questions"],
        Base.metadata.tables["retrieval_runs"],
        Base.metadata.tables["model_runs"],
        Base.metadata.tables["answers"],
        Base.metadata.tables["eval_cases"],
        Base.metadata.tables["eval_runs"],
        Base.metadata.tables["eval_results"],
        Base.metadata.tables["review_items"],
        Base.metadata.tables["approved_faqs"],
        Base.metadata.tables["provider_configs"],
        Base.metadata.tables["tickets"],
        Base.metadata.tables["log_sources"],
        Base.metadata.tables["image_assets"],
        Base.metadata.tables["ocr_results"],
    ]
    Base.metadata.create_all(bind=engine, tables=create_subset)
    log_source_columns = {column["name"] for column in inspect(engine).get_columns("log_sources")}
    assert "content" in log_source_columns
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    catalog_repo = CatalogRepository(session)
    retrieval_repo = RetrievalRepository(session)
    review_repo = ReviewEvalRepository(session)

    product = catalog_repo.add_product(Product(name="FlyingRC F4", slug="flyingrc-f4", description="Flight controller"))
    source = catalog_repo.add_source(Source(product_id=product.id, title="Manual", source_type=SourceType.markdown))
    version = catalog_repo.add_source_version(SourceVersion(source_id=source.id, version_label="v1", content_hash="0" * 64))
    question = retrieval_repo.add_question(Question(product_id=product.id, raw_text="Can USB power servos?", normalized_text="usb servos"))
    run = retrieval_repo.add_retrieval_run(RetrievalRun(question_id=question.id, normalized_query=question.normalized_text))
    model_run = retrieval_repo.add_model_run(ModelRun(provider_type="llm", provider_name="fake", model_name="fake", input_hash="1" * 64))
    answer = retrieval_repo.add_answer(
        Answer(
            question_id=question.id,
            retrieval_run_id=run.id,
            answer_text="No.",
            evidence_sufficiency=EvidenceSufficiency.insufficient,
            confidence=0.2,
            model_run_id=model_run.id,
        )
    )
    eval_case = review_repo.add_eval_case(EvalCase(product_id=product.id, question_text=question.raw_text))
    eval_run = review_repo.add_eval_run(EvalRun(name="MVP eval"))
    eval_result = review_repo.add_eval_result(
        EvalResult(
            eval_run_id=eval_run.id,
            eval_case_id=eval_case.id,
            question_id=question.id,
            retrieval_run_id=run.id,
            answer_id=answer.id,
            recall_at_20=0.0,
            rerank_at_5=0.0,
            citation_support_rate=0.0,
            unsupported_claim_rate=1.0,
            need_review=True,
            failure_category=FailureCategory.insufficient_evidence,
        )
    )
    review_item = review_repo.add_review_item(
        ReviewItem(source_type="eval_failure", question_id=question.id, answer_id=answer.id, eval_result_id=eval_result.id)
    )
    faq = review_repo.add_approved_faq(
        ApprovedFAQ(
            product_id=product.id,
            review_item_id=review_item.id,
            question_text=question.raw_text,
            answer_text="USB is for configuration only.",
            source_id=source.id,
        )
    )
    provider_config = review_repo.add_provider_config(
        ProviderConfig(provider_type="llm", provider_name="fake", model_name="fake-citation-llm")
    )
    ticket = review_repo.add_ticket(Ticket(product_id=product.id, external_id="T-1", title="USB", body="Customer asks.", source_id=source.id))
    log_source = review_repo.add_log_source(LogSource(product_id=product.id, log_type="boot", content="BOOT OK", source_id=source.id))
    image_asset = review_repo.add_image_asset(
        ImageAsset(product_id=product.id, storage_uri="local://image.png", image_type="screenshot", source_id=source.id)
    )
    ocr = review_repo.add_ocr_result(OcrResult(image_asset_id=image_asset.id, provider_name="fake", model_name="fake-ocr", ocr_text="USB"))
    session.commit()
    session.expire_all()

    assert review_repo.list_eval_cases()[0].id == eval_case.id
    assert review_repo.results_for_eval_run(eval_run.id)[0].failure_category == FailureCategory.insufficient_evidence
    assert review_repo.list_review_items()[0].id == review_item.id
    assert faq.source_id == source.id
    assert review_repo.list_provider_configs()[0].id == provider_config.id
    assert ticket.source_id == source.id
    assert log_source.content == "BOOT OK"
    saved_ocr = review_repo.ocr_results_for_image(image_asset.id)[0]
    assert saved_ocr.id == ocr.id
    assert saved_ocr.status == "completed"
