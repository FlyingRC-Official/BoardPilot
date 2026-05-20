from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

import app.models.orm  # noqa: F401
from app.db.base import Base
from app.db.repositories import CatalogRepository
from app.models.schemas import Chunk, Product, ProductAlias, Source, SourceArtifact, SourceType, SourceVersion


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
