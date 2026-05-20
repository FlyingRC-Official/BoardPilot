from datetime import datetime
from typing import Optional

from app.db.session import store
from app.ingestion.tasks import ingest_source_version
from app.models.schemas import IngestionJob


def _error_reason(exc: Exception) -> str:
    return str(exc) or exc.__class__.__name__


def run_ingestion_job(source_version_id, job: Optional[IngestionJob] = None):
    active_job = job or store.add_ingestion_job(IngestionJob(source_version_id=source_version_id))
    active_job.status = "running"
    active_job.updated_at = datetime.utcnow()
    store.ingestion_jobs[active_job.id] = active_job
    try:
        chunks = ingest_source_version(store, source_version_id)
    except Exception as exc:
        active_job.status = "failed"
        active_job.error_message = _error_reason(exc)
        if source_version_id in store.source_versions:
            version = store.source_versions[source_version_id]
            version.status = "failed"
            version.error_message = active_job.error_message
            store.source_versions[version.id] = version
        active_job.updated_at = datetime.utcnow()
        store.ingestion_jobs[active_job.id] = active_job
        return active_job, []
    active_job.status = "completed"
    active_job.error_message = ""
    active_job.chunk_count = len(chunks)
    if source_version_id in store.source_versions:
        version = store.source_versions[source_version_id]
        version.error_message = ""
        store.source_versions[version.id] = version
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
