from sqlalchemy import create_engine, inspect

import app.models.orm  # noqa: F401
from app.db.base import Base


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
