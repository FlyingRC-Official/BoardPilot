from datetime import datetime
from typing import Optional

from app.db.session import store
from app.ingestion.tasks import ingest_source_version
from app.models.schemas import IngestionJob


def run_ingestion_job(source_version_id, job: Optional[IngestionJob] = None):
    active_job = job or store.add_ingestion_job(IngestionJob(source_version_id=source_version_id))
    active_job.status = "running"
    active_job.updated_at = datetime.utcnow()
    store.ingestion_jobs[active_job.id] = active_job
    try:
        chunks = ingest_source_version(store, source_version_id)
    except Exception as exc:
        active_job.status = "failed"
        active_job.error_message = str(exc)
        active_job.updated_at = datetime.utcnow()
        store.ingestion_jobs[active_job.id] = active_job
        raise
    active_job.status = "completed"
    active_job.error_message = ""
    active_job.chunk_count = len(chunks)
    active_job.updated_at = datetime.utcnow()
    store.ingestion_jobs[active_job.id] = active_job
    return active_job, chunks


def retry_ingestion_job(job_id):
    job = store.ingestion_jobs[job_id]
    job.status = "queued"
    job.error_message = ""
    job.chunk_count = 0
    job.updated_at = datetime.utcnow()
    return run_ingestion_job(job.source_version_id, job)
