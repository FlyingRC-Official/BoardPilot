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
- Added a repeatable 20-case hardware-support Eval seed corpus and Eval page seed action.
- Added reviewer-edited answer controls before ApprovedFAQ conversion.
- Added product alias detection during Ask with normalized query expansion and soft product boosts.
- Added minimal role-aware request context through `X-BoardPilot-User` and `X-BoardPilot-Role` headers.
- Guarded protected mutating endpoints for admin, support, and reviewer roles while keeping local development defaulted to admin.
- Added saved LLM ModelRun records for answer generation and linked Answers to `model_run_id`.
- Added saved fake ChunkEmbedding records during ingestion and a chunk embedding inspection endpoint.
- Expanded EvalRun summaries with evidence sufficiency rate, failure-category distribution, latency p50/p95, and model cost placeholder.
- Enforced explicit failure categories before review approval or rejection.
- Implemented in-memory IngestionJob records for create, list, get, and retry APIs.
- Added typed in-memory AuditLog records and an admin audit log endpoint.
- Audit logging now records source updates, review decisions, ApprovedFAQ creation, and EvalCase creation/modification with before/after context where available.
- Added a recent audit-event table to the Review page.
- Added Sources page controls for creating product aliases used by Ask-time alias detection.
- Added provider configuration records, admin-only provider config APIs, and provider config audit events.
- Implemented typed ticket, log, image, and OCR records that create source material and chunks for retrieval.
- Added EvalRun comparison endpoint and Eval page delta table for comparing consecutive runs.
- ReviewItem to EvalCase conversion now preserves expected source ids, chunk ids, and reviewer-edited answer points for regression coverage.
- Review page now supports editable failure categories and reviewer notes, backed by validated and audited ReviewItem updates.
- Eval page now surfaces failure-category distribution from EvalRun summary metrics.
- Added a Settings page for creating, editing, deleting, and listing provider configuration records.
- Added ReviewItem detail API/UI that shows the linked question, generated answer, evidence pack, and retrieval trace.

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

- API tests: 22 passed.
- Alembic upgrade command: passed against the default local database URL.
- Next.js production build: passed.
- API health: HTTP 200.
- Web routes `/ask`, `/sources`, `/eval`, and `/review`: HTTP 200.

## Important MVP Gaps

- API runtime persistence is still in-memory; SQLAlchemy models and Alembic migration exist but the service layer has not yet been switched to database-backed repositories.
- IngestionJob APIs now persist job status in memory and support retry; execution still runs inline instead of through Redis-backed workers.
- File upload handling exists for parser-aware text sources and PDFs; image OCR is still a fake-provider/manual-description placeholder.
- Tickets, logs, image manual descriptions, and OCR text now enter the source/chunk pipeline; OCR provider remains fake.
- EvalRun can run the required 20-case seed corpus and compare numeric metric deltas between two runs.
- Product aliases are detected and saved on Questions; auto-detected products soft-boost retrieval while explicit product selection remains a hard filter.
- Minimal role-aware access control is present; it is header-based for MVP and still needs real authentication/session management.
- Core audit events are inspectable through `GET /audit-logs`; persistence remains in-memory until SQLAlchemy repositories are wired.
- Answer generation now records provider, model, input hash, prompt version, latency, token estimates, status, and errors in ModelRun records.
- Ingested chunks now store provider/model-specific embedding records for retrieval comparison and re-indexing.
- EvalRun summaries now include the MVP-required aggregate metric families; comparison UI remains minimal.
- Review approval/rejection now fails without an explicit failure category.
- Authentication and role enforcement are not implemented.
- Audit logging exists as an in-memory event list and needs durable storage.
- ApprovedFAQ conversion re-ingests reviewer-edited FAQ content into retrieval, EvalCase conversion keeps expected evidence, reviewers can save notes/failure categories, and Review detail shows linked question/answer/evidence/trace; review still needs durable database persistence and richer eval-result context.
- The web workbench is functional but has not been visually verified in the in-app browser because the browser execution tool was unavailable in this session.

## Recommended Next Subtasks

1. Replace the in-memory API store with SQLAlchemy-backed repositories.
2. Add parser-specific PDF extraction, CSV normalization, and image OCR handling for uploaded artifacts.
3. Move ingestion and embedding jobs to Redis-backed workers.
4. Replace header-based local role context with real authentication/session management.
5. Add richer eval-result context to Review detail.
6. Add model-cost assumptions and provider-selection wiring into runtime provider calls.
