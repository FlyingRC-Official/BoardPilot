import hashlib
import re
from uuid import UUID

from app.core.config import settings
from app.db.store import InMemoryStore
from app.ingestion.parsers.csv_faq import parse_csv_faq
from app.ingestion.parsers.image_stub import parse_image_description
from app.ingestion.parsers.markdown import parse_markdown
from app.ingestion.parsers.pdf import parse_pdf_bytes, parse_pdf_text
from app.ingestion.parsers.text_log import parse_text_log
from app.ingestion.parsers.webpage import parse_webpage_snapshot
from app.ingestion.tasks import ingest_source_version
from app.models.schemas import Source, SourceArtifact, SourceCreate, SourceType, SourceVersion, SourceVersionCreate, WebpageSnapshotCreate
from app.storage.local import LocalStorageProvider


def safe_filename(filename: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", filename.strip())
    return clean or "artifact.txt"


def parser_version_for(source_type: SourceType) -> str:
    return f"mvp-{source_type.value}-parser-v1"


def parse_source_content(source_type: SourceType, text: str) -> str:
    parsers = {
        SourceType.markdown: parse_markdown,
        SourceType.csv_faq: parse_csv_faq,
        SourceType.ticket_export: parse_csv_faq,
        SourceType.text_log: parse_text_log,
        SourceType.pdf: parse_pdf_text,
        SourceType.image: parse_image_description,
        SourceType.approved_faq: parse_markdown,
        SourceType.manual_note: parse_markdown,
        SourceType.webpage: parse_webpage_snapshot,
    }
    return parsers.get(source_type, parse_markdown)(text)


def parse_artifact_text(source: Source, content: bytes) -> str:
    # Source-type parsers normalize uploaded artifacts before chunking. PDF uses
    # pypdf when possible and falls back to decoded text for test fixtures.
    if source.source_type == SourceType.pdf:
        return parse_pdf_text(parse_pdf_bytes(content))
    decoded = content.decode("utf-8", errors="replace")
    return parse_source_content(source.source_type, decoded)


def create_source(store: InMemoryStore, payload: SourceCreate) -> Source:
    if payload.product_id not in store.products:
        raise KeyError("product not found")
    return store.add_source(Source(**payload.model_dump()))


def list_sources(store: InMemoryStore) -> list[Source]:
    return list(store.sources.values())


def create_source_version(store: InMemoryStore, source_id: UUID, payload: SourceVersionCreate) -> tuple[SourceVersion, SourceArtifact, list]:
    if source_id not in store.sources:
        raise KeyError("source not found")
    source = store.sources[source_id]
    content_hash = hashlib.sha256(payload.content.encode("utf-8")).hexdigest()
    parsed_content = parse_source_content(source.source_type, payload.content)
    version = store.add_source_version(
        SourceVersion(
            source_id=source_id,
            version_label=payload.version_label,
            content_hash=content_hash,
            parser_version=payload.parser_version if payload.parser_version != "mvp-text-v1" else parser_version_for(source.source_type),
        )
    )
    artifact = store.add_artifact(
        SourceArtifact(
            source_version_id=version.id,
            artifact_type="original",
            storage_uri=f"memory://sources/{source_id}/{version.id}",
            size_bytes=len(payload.content.encode("utf-8")),
            checksum=content_hash,
            metadata_json={"source_type": source.source_type.value},
            content=parsed_content,
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
            parser_version=parser_version_for(source.source_type),
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
            metadata_json={"original_filename": filename, "source_type": source.source_type.value},
            content=parsed_text,
        )
    )
    chunks = ingest_source_version(store, version.id)
    return version, artifact, chunks


def create_webpage_snapshot_version(
    store: InMemoryStore,
    source_id: UUID,
    payload: WebpageSnapshotCreate,
) -> tuple[SourceVersion, SourceArtifact, list]:
    if source_id not in store.sources:
        raise KeyError("source not found")
    source = store.sources[source_id]
    if source.source_type != SourceType.webpage:
        raise ValueError("webpage snapshots require a webpage source")
    checksum = hashlib.sha256(f"{payload.url}\n{payload.html}".encode("utf-8")).hexdigest()
    parsed_text = parse_webpage_snapshot(payload.html)
    version = store.add_source_version(
        SourceVersion(
            source_id=source_id,
            version_label=payload.version_label or "snapshot",
            content_hash=checksum,
            parser_version=parser_version_for(SourceType.webpage),
            status="created",
        )
    )
    artifact = store.add_artifact(
        SourceArtifact(
            source_version_id=version.id,
            artifact_type="webpage_snapshot",
            storage_uri=payload.url,
            mime_type="text/html",
            size_bytes=len(payload.html.encode("utf-8")),
            checksum=checksum,
            metadata_json={"source_type": source.source_type.value, "snapshot_url": payload.url},
            content=parsed_text,
        )
    )
    chunks = ingest_source_version(store, version.id)
    return version, artifact, chunks
