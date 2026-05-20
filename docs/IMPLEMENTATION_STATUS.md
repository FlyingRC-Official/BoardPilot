# BoardPilot Implementation Status

Updated: 2026-05-20

## Completed in Current MVP Slice

- Initialized the repository against `https://github.com/FlyingRC-Official/BoardPilot.git`.
- Added a runnable FastAPI backend.
- Added in-memory persistence for local development and tests.
- Added core schemas for products, aliases, sources, versions, artifacts, chunks, questions, retrieval runs, candidates, evidence, answers, eval, and review.
- Added fake LLM, embedding, reranker, and OCR provider abstractions.
- Added source ingestion from text content into deduplicated chunks.
- Added hybrid retrieval using keyword overlap, fake vector similarity, merge/dedup, rerank, and saved evidence.
- Added citation-backed answer generation that only cites saved Evidence ids.
- Added review routing for partial or insufficient evidence.
- Added EvalCase and EvalRun flow with MVP metrics.
- Added a Next.js workbench with Ask, Sources, Eval, and Review pages.
- Added Docker Compose definitions for API, web, Postgres/pgvector, and Redis.
- Added deployment and eval guide documents.

## Verified

```bash
api/.venv/bin/pytest api/app/tests
npm run build
curl -sS http://127.0.0.1:8000/health
curl -sS -I http://127.0.0.1:3000/ask
curl -sS -I http://127.0.0.1:3000/sources
curl -sS -I http://127.0.0.1:3000/eval
curl -sS -I http://127.0.0.1:3000/review
```

Results:

- API tests: 5 passed.
- Next.js production build: passed.
- API health: HTTP 200.
- Web routes `/ask`, `/sources`, `/eval`, and `/review`: HTTP 200.

## Important MVP Gaps

- Persistence is still in-memory; Postgres models and Alembic migrations need to replace it.
- Redis-backed background workers are scaffolded but ingestion currently runs inline.
- File upload handling is not implemented; source versions currently accept text content through JSON.
- PDF parsing is a placeholder that accepts extracted text; real PDF extraction should be added.
- Image OCR is a fake-provider placeholder.
- Authentication and role enforcement are not implemented.
- Audit logging exists as an in-memory event list and needs durable storage.
- ApprovedFAQ conversion is a status transition placeholder and does not yet re-ingest FAQ source content.
- The web workbench is functional but has not been visually verified in the in-app browser because the browser execution tool was unavailable in this session.

## Recommended Next Subtasks

1. Replace the in-memory store with SQLAlchemy models and Alembic migrations for the required schema.
2. Add multipart source uploads and local filesystem storage through `StorageProvider`.
3. Move ingestion and embedding jobs to Redis-backed workers.
4. Implement ApprovedFAQ creation and re-ingestion.
5. Add authentication with role-aware guards for admin, support, reviewer, and viewer.
6. Expand eval seed data to the required 20 cases and add failure-category reporting UI.

