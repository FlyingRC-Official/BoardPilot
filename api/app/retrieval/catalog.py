from typing import Optional
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.repositories import CatalogRepository
from app.db.store import InMemoryStore


def hydrate_retrieval_catalog(store: InMemoryStore, session: Session, product_id: Optional[UUID] = None) -> dict:
    try:
        repo = CatalogRepository(session)
        products = repo.list_products()
        sources = repo.list_sources()
    except SQLAlchemyError:
        session.rollback()
        return {"products": 0, "aliases": 0, "sources": 0, "versions": 0, "chunks": 0, "embeddings": 0}

    alias_count = 0
    for product in products:
        store.products[product.id] = product
        try:
            aliases = repo.aliases_for_product(product.id)
        except SQLAlchemyError:
            session.rollback()
            aliases = []
        for alias in aliases:
            store.product_aliases[alias.id] = alias
            alias_count += 1

    if product_id:
        sources = [source for source in sources if source.product_id == product_id]

    version_count = 0
    chunk_count = 0
    embedding_count = 0
    for source in sources:
        store.sources[source.id] = source
        try:
            versions = repo.versions_for_source(source.id)
        except SQLAlchemyError:
            session.rollback()
            versions = []
        for version in versions:
            store.source_versions[version.id] = version
            version_count += 1
            try:
                chunks = repo.chunks_for_version(version.id)
            except SQLAlchemyError:
                session.rollback()
                chunks = []
            for chunk in chunks:
                store.chunks[chunk.id] = chunk
                store.chunk_hashes_by_version[chunk.source_version_id].add(chunk.content_hash)
                chunk_count += 1
                try:
                    embeddings = repo.embeddings_for_chunk(chunk.id)
                except SQLAlchemyError:
                    session.rollback()
                    embeddings = []
                for embedding in embeddings:
                    store.chunk_embeddings[embedding.id] = embedding
                    embedding_count += 1

    return {
        "products": len(products),
        "aliases": alias_count,
        "sources": len(sources),
        "versions": version_count,
        "chunks": chunk_count,
        "embeddings": embedding_count,
    }
