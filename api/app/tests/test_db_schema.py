from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

import app.models.orm  # noqa: F401
from app.db.base import Base
from app.db.repositories import CatalogRepository, RetrievalRepository, ReviewEvalRepository, RuntimeRepository
from app.models.schemas import (
    Answer,
    ApprovedFAQ,
    AuditLog,
    Chunk,
    EvalCase,
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
    Product,
    ProductAlias,
    ProviderConfig,
    Question,
    QuestionAttachment,
    RetrievalCandidate,
    RetrievalRun,
    ReviewItem,
    Source,
    SourceArtifact,
    SourceType,
    SourceVersion,
    Ticket,
)


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
    assert review_repo.ocr_results_for_image(image_asset.id)[0].id == ocr.id
