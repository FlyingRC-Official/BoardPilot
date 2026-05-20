from __future__ import annotations

import argparse
import logging
import time

from app.core.config import settings
from app.db.repositories import CatalogRepository, ReviewEvalRepository, RuntimeRepository
from app.db.session import SessionLocal
from app.ingestion.jobs import run_ingestion_job
from app.ingestion.queue import QUEUE_NAME, decode_ingestion_job, encode_ingestion_job
from app.db.session import store
from app.models.schemas import FailureCategory, IngestionJob, ReviewItem
from app.providers.config_store import hydrate_provider_configs

logger = logging.getLogger("boardpilot.ingestion_worker")


def hydrate_source_version(source_version_id) -> bool:
    session = SessionLocal()
    try:
        catalog = CatalogRepository(session)
        version = catalog.get_source_version(source_version_id)
        if not version:
            return False
        source = catalog.get_source(version.source_id)
        if not source:
            return False
        store.source_versions[version.id] = version
        store.sources[source.id] = source
        if source.product_id:
            product = catalog.get_product(source.product_id)
            if product:
                store.products[product.id] = product
        for artifact in catalog.artifacts_for_version(version.id):
            store.source_artifacts[artifact.id] = artifact
        for chunk in catalog.chunks_for_version(version.id):
            store.chunks[chunk.id] = chunk
            store.chunk_hashes_by_version[chunk.source_version_id].add(chunk.content_hash)
            for embedding in catalog.embeddings_for_chunk(chunk.id):
                store.chunk_embeddings[embedding.id] = embedding
        return True
    finally:
        session.close()


def persist_ingestion_result(job: IngestionJob, chunks) -> None:
    session = SessionLocal()
    try:
        RuntimeRepository(session).add_ingestion_job(job)
        catalog = CatalogRepository(session)
        version = store.source_versions.get(job.source_version_id)
        if version:
            catalog.add_source_version(version)
            if version.status == "failed" and version.error_message.strip():
                review_item = ReviewItem(
                    source_type="source_issue",
                    priority=1,
                    failure_category=FailureCategory.bad_parse,
                    reviewer_notes=f"SourceVersion {version.id} failed ingestion: {version.error_message}",
                )
                store.review_items[review_item.id] = review_item
                ReviewEvalRepository(session).add_review_item(review_item)
        catalog.add_chunks(chunks)
        session.commit()
    finally:
        session.close()

    embeddings = [embedding for chunk in chunks for embedding in store.embeddings_for_chunk(chunk.id)]
    if not embeddings:
        return
    session = SessionLocal()
    try:
        CatalogRepository(session).add_chunk_embeddings(embeddings)
        session.commit()
    finally:
        session.close()


def process_message(raw_message: bytes | str) -> None:
    message = decode_ingestion_job(raw_message)
    session = SessionLocal()
    try:
        job = RuntimeRepository(session).get_ingestion_job(message.job_id) if message.job_id else None
    finally:
        session.close()
    if not job:
        job = IngestionJob(source_version_id=message.source_version_id, id=message.job_id) if message.job_id else None
    if job:
        store.ingestion_jobs[job.id] = job
    if not hydrate_source_version(message.source_version_id):
        if job:
            job.status = "failed"
            job.error_message = "source version not found"
            persist_ingestion_result(job, [])
        raise KeyError("source version not found")
    session = SessionLocal()
    try:
        hydrate_provider_configs(store, session)
    finally:
        session.close()
    job, chunks = run_ingestion_job(message.source_version_id, job)
    persist_ingestion_result(job, chunks)


def run_worker(once: bool = False, poll_timeout_seconds: int = 5) -> None:
    from redis import Redis

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    redis_client = Redis.from_url(settings.redis_url)
    logger.info("listening queue=%s redis=%s", QUEUE_NAME, settings.redis_url)
    while True:
        item = redis_client.blpop(QUEUE_NAME, timeout=poll_timeout_seconds)
        if item:
            _queue_name, raw_message = item
            process_message(raw_message)
        if once:
            return
        time.sleep(0.1)


def main() -> None:
    parser = argparse.ArgumentParser(description="BoardPilot ingestion worker")
    parser.add_argument("--once", action="store_true", help="Poll once and exit")
    parser.add_argument("--poll-timeout-seconds", type=int, default=5)
    args = parser.parse_args()
    run_worker(once=args.once, poll_timeout_seconds=args.poll_timeout_seconds)


if __name__ == "__main__":
    main()
