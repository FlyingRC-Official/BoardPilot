from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import UUID

from app.core.config import settings
from app.models.schemas import IngestionJob

QUEUE_NAME = "boardpilot:ingestion_jobs"


@dataclass
class IngestionJobMessage:
    source_version_id: UUID
    job_id: UUID | None = None


def encode_ingestion_job(source_version_id: UUID, job_id: UUID | None = None) -> str:
    payload = {"source_version_id": str(source_version_id)}
    if job_id:
        payload["job_id"] = str(job_id)
    return json.dumps(payload, sort_keys=True)


def decode_ingestion_job(raw_message: bytes | str) -> IngestionJobMessage:
    payload = json.loads(raw_message.decode("utf-8") if isinstance(raw_message, bytes) else raw_message)
    return IngestionJobMessage(
        source_version_id=UUID(str(payload["source_version_id"])),
        job_id=UUID(str(payload["job_id"])) if payload.get("job_id") else None,
    )


def get_redis_client():
    from redis import Redis

    return Redis.from_url(settings.redis_url)


def enqueue_ingestion_job(job: IngestionJob) -> None:
    redis_client = get_redis_client()
    redis_client.rpush(QUEUE_NAME, encode_ingestion_job(job.source_version_id, job.id))
