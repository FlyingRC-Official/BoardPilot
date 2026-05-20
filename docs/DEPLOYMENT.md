# BoardPilot Private Deployment

BoardPilot is designed as a small private stack:

- `web`: Next.js workbench.
- `api`: FastAPI backend.
- `db`: Postgres with pgvector.
- `redis`: queue backend for ingestion and embedding work.
- `storage`: local filesystem mount for originals and derived artifacts.

## Start

```bash
cp .env.example .env
docker compose up --build
```

## Privacy Boundary

The default provider config is fake/local. Source content should not leave the deployment unless an admin intentionally enables an external LLM, embedding, reranker, or OCR provider.

## MVP Gaps

The current implementation is a runnable development slice. Before production use, replace in-memory persistence with Postgres migrations, move ingestion into Redis-backed workers, add authentication, and enforce durable audit retention.

