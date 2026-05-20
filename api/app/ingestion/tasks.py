from app.ingestion.chunking import chunk_text
from app.models.schemas import ChunkEmbedding, now
from app.providers.embedding import run_configured_embedding


def ingest_source_version(store, source_version_id):
    version = store.source_versions[source_version_id]
    source = store.sources[version.source_id]
    artifacts = [a for a in store.source_artifacts.values() if a.source_version_id == source_version_id]
    text = "\n\n".join(a.content for a in artifacts if a.content)
    provider_config = store.active_provider_config("embedding")
    chunks = chunk_text(version.id, source.product_id, text)
    embedding_results = {}
    for chunk in chunks:
        embedding = run_configured_embedding(provider_config, chunk.content)
        if embedding.error_message:
            raise RuntimeError(embedding.error_message)
        if not embedding.vector:
            raise RuntimeError("embedding provider returned an empty vector")
        embedding_results[chunk.id] = embedding
    inserted = store.add_chunks(chunks)
    for chunk in inserted:
        embedding = embedding_results[chunk.id]
        provider_name = provider_config.provider_name if provider_config else embedding.provider_name
        model_name = provider_config.model_name if provider_config else embedding.model_name
        store.add_chunk_embedding(
            ChunkEmbedding(
                chunk_id=chunk.id,
                provider_name=provider_name,
                model_name=model_name,
                embedding_dimension=len(embedding.vector),
                vector=embedding.vector,
            )
        )
    version.status = "ingested"
    version.updated_at = now()
    store.source_versions[version.id] = version
    return inserted
