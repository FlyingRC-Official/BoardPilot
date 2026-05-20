# BoardPilot Private Deployment

BoardPilot is designed as a small private stack:

- `web`: Next.js workbench.
- `api`: FastAPI backend.
- `worker`: ingestion worker process for Redis queue jobs.
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

## API Key Gate

Local development leaves `BOARDPILOT_API_KEY` empty, so the workbench can use the role headers directly. In a private deployment, set `BOARDPILOT_API_KEY` for the API and worker, and set the same value as `NEXT_PUBLIC_BOARDPILOT_API_KEY` for the bundled private web workbench so browser requests include `X-BoardPilot-API-Key`.

## MVP Gaps

The current implementation is a runnable development slice. Before production use, replace remaining in-memory service hydration, add real user sessions, and enforce durable audit retention.
