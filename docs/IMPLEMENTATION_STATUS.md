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
- Added SQLAlchemy ORM models for the required MVP schema.
- Added an initial Alembic migration foundation with pgvector extension setup for Postgres.
- Added multipart source artifact upload backed by local filesystem storage.
- Added Sources page upload control for storing and ingesting source artifacts.
- Implemented ReviewItem to ApprovedFAQ conversion with FAQ source re-ingestion.
- Added source-type parser routing for Markdown, CSV/FAQ, ticket exports, text logs, image descriptions, approved FAQs, and text-extracted PDFs.
- Added `pypdf`-backed PDF text extraction with a decoded-text fallback.

## Verified

```bash
api/.venv/bin/pytest api/app/tests
cd api && PYTHONPATH=. .venv/bin/alembic upgrade head
npm run build
curl -sS http://127.0.0.1:8000/health
curl -sS -I http://127.0.0.1:3000/ask
curl -sS -I http://127.0.0.1:3000/sources
curl -sS -I http://127.0.0.1:3000/eval
curl -sS -I http://127.0.0.1:3000/review
```

Results:

- API tests: 11 passed.
- Alembic upgrade command: passed against the default local database URL.
- Next.js production build: passed.
- API health: HTTP 200.
- Web routes `/ask`, `/sources`, `/eval`, and `/review`: HTTP 200.

## Important MVP Gaps

- API runtime persistence is still in-memory; SQLAlchemy models and Alembic migration exist but the service layer has not yet been switched to database-backed repositories.
- Redis-backed background workers are scaffolded but ingestion currently runs inline.
- File upload handling exists for parser-aware text sources and PDFs; image OCR is still a fake-provider/manual-description placeholder.
- Authentication and role enforcement are not implemented.
- Audit logging exists as an in-memory event list and needs durable storage.
- ApprovedFAQ conversion re-ingests FAQ content into retrieval; it still needs reviewer editing UI polish and durable database persistence.
- The web workbench is functional but has not been visually verified in the in-app browser because the browser execution tool was unavailable in this session.

## Recommended Next Subtasks

1. Replace the in-memory API store with SQLAlchemy-backed repositories.
2. Add parser-specific PDF extraction, CSV normalization, and image OCR handling for uploaded artifacts.
3. Move ingestion and embedding jobs to Redis-backed workers.
4. Add authentication with role-aware guards for admin, support, reviewer, and viewer.
5. Expand eval seed data to the required 20 cases and add failure-category reporting UI.
6. Add reviewer editing controls before FAQ conversion.
