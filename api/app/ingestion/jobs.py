from app.db.session import store
from app.ingestion.tasks import ingest_source_version


def run_ingestion_job(source_version_id):
    return ingest_source_version(store, source_version_id)

