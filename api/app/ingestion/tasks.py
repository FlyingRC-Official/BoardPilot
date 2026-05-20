from app.ingestion.chunking import chunk_text
from app.models.schemas import ChunkEmbedding
from app.providers.embedding import embedding_provider


def ingest_source_version(store, source_version_id):
    version = store.source_versions[source_version_id]
    source = store.sources[version.source_id]
    artifacts = [a for a in store.source_artifacts.values() if a.source_version_id == source_version_id]
    text = "\n\n".join(a.content for a in artifacts if a.content)
    chunks = chunk_text(version.id, source.product_id, text)
    inserted = store.add_chunks(chunks)
    provider_config = store.active_provider_config("embedding")
    for chunk in inserted:
        embedding = embedding_provider.embed(chunk.content)
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
    store.source_versions[version.id] = version
    return inserted
