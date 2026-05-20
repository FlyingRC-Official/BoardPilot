from app.ingestion.chunking import chunk_text


def ingest_source_version(store, source_version_id):
    version = store.source_versions[source_version_id]
    source = store.sources[version.source_id]
    artifacts = [a for a in store.source_artifacts.values() if a.source_version_id == source_version_id]
    text = "\n\n".join(a.content for a in artifacts if a.content)
    chunks = chunk_text(version.id, source.product_id, text)
    inserted = store.add_chunks(chunks)
    version.status = "ingested"
    store.source_versions[version.id] = version
    return inserted

