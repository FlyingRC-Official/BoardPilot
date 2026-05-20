import hashlib
from uuid import UUID

from app.db.store import InMemoryStore
from app.ingestion.tasks import ingest_source_version
from app.models.schemas import Source, SourceArtifact, SourceCreate, SourceVersion, SourceVersionCreate


def create_source(store: InMemoryStore, payload: SourceCreate) -> Source:
    if payload.product_id not in store.products:
        raise KeyError("product not found")
    return store.add_source(Source(**payload.model_dump()))


def list_sources(store: InMemoryStore) -> list[Source]:
    return list(store.sources.values())


def create_source_version(store: InMemoryStore, source_id: UUID, payload: SourceVersionCreate) -> tuple[SourceVersion, SourceArtifact, list]:
    if source_id not in store.sources:
        raise KeyError("source not found")
    content_hash = hashlib.sha256(payload.content.encode("utf-8")).hexdigest()
    version = store.add_source_version(
        SourceVersion(
            source_id=source_id,
            version_label=payload.version_label,
            content_hash=content_hash,
            parser_version=payload.parser_version,
        )
    )
    artifact = store.add_artifact(
        SourceArtifact(
            source_version_id=version.id,
            artifact_type="original",
            storage_uri=f"memory://sources/{source_id}/{version.id}",
            size_bytes=len(payload.content.encode("utf-8")),
            checksum=content_hash,
            content=payload.content,
        )
    )
    chunks = ingest_source_version(store, version.id)
    return version, artifact, chunks

