import hashlib
import re
from uuid import UUID

from app.core.config import settings
from app.db.store import InMemoryStore
from app.ingestion.tasks import ingest_source_version
from app.models.schemas import Source, SourceArtifact, SourceCreate, SourceVersion, SourceVersionCreate
from app.storage.local import LocalStorageProvider


def safe_filename(filename: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", filename.strip())
    return clean or "artifact.txt"


def parse_artifact_text(source: Source, content: bytes) -> str:
    # MVP parsers consume text. Binary PDF/OCR providers are still provider-backed
    # follow-up work, so undecodable bytes are preserved as replacement chars.
    return content.decode("utf-8", errors="replace")


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


def create_uploaded_source_version(
    store: InMemoryStore,
    source_id: UUID,
    version_label: str,
    filename: str,
    content_type: str,
    content: bytes,
) -> tuple[SourceVersion, SourceArtifact, list]:
    if source_id not in store.sources:
        raise KeyError("source not found")
    source = store.sources[source_id]
    checksum = hashlib.sha256(content).hexdigest()
    parsed_text = parse_artifact_text(source, content)
    storage = LocalStorageProvider(settings.storage_root)
    storage_uri = storage.save_bytes(f"originals/{source_id}/{checksum}-{safe_filename(filename)}", content)
    version = store.add_source_version(
        SourceVersion(
            source_id=source_id,
            version_label=version_label or "uploaded",
            content_hash=checksum,
            parser_version="mvp-upload-text-v1",
            status="created",
        )
    )
    artifact = store.add_artifact(
        SourceArtifact(
            source_version_id=version.id,
            artifact_type="original",
            storage_uri=storage_uri,
            mime_type=content_type or "application/octet-stream",
            size_bytes=len(content),
            checksum=checksum,
            metadata_json={"original_filename": filename},
            content=parsed_text,
        )
    )
    chunks = ingest_source_version(store, version.id)
    return version, artifact, chunks
