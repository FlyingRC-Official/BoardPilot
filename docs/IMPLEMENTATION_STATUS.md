# BoardPilot Implementation Status

Updated: 2026-05-21

## Completed in Current MVP Slice

- Initialized the repository against `https://github.com/FlyingRC-Official/BoardPilot.git`.
- Added a runnable FastAPI backend.
- Added in-memory persistence for local development and tests.
- Added core schemas for products, aliases, sources, versions, artifacts, chunks, questions, retrieval runs, candidates, evidence, answers, eval, and review.
- Added fake LLM, embedding, reranker, and OCR provider abstractions.
- Added direct fake-provider contract tests for structured LLM, embedding, reranker, and OCR result metadata.
- Added source ingestion from text content into deduplicated chunks.
- Added hybrid retrieval using keyword overlap, fake vector similarity, merge/dedup, rerank, and saved evidence.
- Retrieval now saves keyword, vector, merged, and reranked candidate stages for trace inspection.
- Added citation-backed answer generation that only cites saved Evidence ids.
- Added review routing for partial or insufficient evidence.
- Added EvalCase and EvalRun flow with MVP metrics.
- Added a Next.js workbench with Ask, Sources, Eval, and Review pages.
- Added Docker Compose definitions for API, web, Postgres/pgvector, and Redis.
- Docker Compose now health-gates Postgres, Redis, API, web, and worker startup, and the API container runs Alembic migrations before serving.
- `.env.example` now documents private-deployment variables, and the API Docker image honors the documented `BOARDPILOT_API_HOST` and `BOARDPILOT_API_PORT` settings.
- Docker Compose now passes the documented `BOARDPILOT_API_HOST` and `BOARDPILOT_API_PORT` settings into the API container.
- Added static deployment contract tests for the Compose service set, private-deployment environment variables, API migration startup, pgvector, Redis, and local storage mount.
- Added deployment and eval guide documents.
- Health, version, and provider metadata endpoints are covered by API regression tests.
- Added SQLAlchemy ORM models for the required MVP schema.
- Added an initial Alembic migration foundation with pgvector extension setup for Postgres.
- Added multipart source artifact upload backed by local filesystem storage.
- Source artifact attachment now honors the requested SourceVersion URL id instead of creating a separate SourceVersion.
- Source-version service hydration now restores existing artifacts, chunks, and chunk hashes before re-ingestion.
- SourceVersion records now persist failed ingestion status and error messages.
- Failed source-version ingestion now creates source-issue ReviewItems with bad-parse failure categories.
- Failed ticket, log, and OCR source ingestion now creates source-issue ReviewItems with bad-parse failure categories.
- Added Sources page upload control for storing and ingesting source artifacts.
- Implemented ReviewItem to ApprovedFAQ conversion with FAQ source re-ingestion.
- Added source-type parser routing for Markdown, CSV/FAQ, ticket exports, text logs, image descriptions, approved FAQs, and text-extracted PDFs.
- CSV/FAQ parsing now normalizes common support-export headers, BOM-prefixed files, whitespace, optional context fields, and headerless two-column rows.
- Added `pypdf`-backed PDF text extraction with a decoded-text fallback.
- Uploaded PDF files that look like real PDFs now fail ingestion with a saved error and source-issue ReviewItem when text extraction fails or yields no text, instead of chunking replacement-decoded binary content.
- Source version creation and manual artifact additions now reject blank content before ingestion so empty source artifacts are not silently persisted.
- Added a repeatable 20-case hardware-support Eval seed corpus and Eval page seed action.
- Eval seed action now persists the generated seed SourceVersion, artifact, chunks, and expected chunk references through SQLAlchemy.
- Added reviewer-edited answer controls before ApprovedFAQ conversion.
- Added product alias detection during Ask with normalized query expansion and soft product boosts.
- Added minimal role-aware request context through `X-BoardPilot-User` and `X-BoardPilot-Role` headers.
- Added first-class `maintainer` and `evaluator` request roles mapped to the required source-maintenance and eval workflows.
- Added optional `BOARDPILOT_API_KEY` enforcement for private deployments, with web workbench support through `NEXT_PUBLIC_BOARDPILOT_API_KEY`.
- Added signed session tokens through `POST /sessions`, `X-BoardPilot-Session` and `Authorization: Bearer` request support, configurable default/max token TTLs, and bundled workbench support through `NEXT_PUBLIC_BOARDPILOT_SESSION_TOKEN`.
- Session token issuance is audit logged without persisting the token secret itself.
- Session issuance can now enforce an operator-managed `BOARDPILOT_USERS_JSON` user/role allowlist.
- Configured `BOARDPILOT_API_KEY` now protects read endpoints as well as role-aware write endpoints, while leaving health checks and CORS preflight available.
- Guarded protected mutating endpoints for admin, support, maintainer, reviewer, and evaluator roles while keeping local development defaulted to admin.
- Ask requests now use the role/API-key request context and persist the submitting user id on Question records.
- Added saved LLM ModelRun records for answer generation and linked Answers to `model_run_id`.
- Added saved fake ChunkEmbedding records during ingestion and a chunk embedding inspection endpoint.
- Expanded EvalRun summaries with evidence sufficiency rate, failure-category distribution, latency p50/p95, and model cost placeholder.
- Enforced explicit failure categories before review approval or rejection.
- Review approval, rejection, source-update-needed, and review-item edit paths now validate failure categories consistently before mutating review state.
- ReviewItem source types are now schema-limited to the documented review buckets: low-confidence answer, insufficient evidence, user feedback, eval failure, and source issue.
- Review decision and conversion audit events now include before/after review-item state for stronger traceability.
- Implemented in-memory IngestionJob records for create, list, get, and retry APIs.
- Added typed in-memory AuditLog records and an admin audit log endpoint.
- Audit logging now records source updates, review decisions, ApprovedFAQ creation, and EvalCase creation/modification with before/after context where available.
- Added a recent audit-event table to the Review page.
- Added Sources page controls for creating product aliases used by Ask-time alias detection.
- Added provider configuration records, admin-only provider config APIs, and provider config audit events.
- Provider configuration create and patch paths now reject provider types outside the documented LLM, embedding, reranker, and OCR set.
- Provider configuration patch and product patch endpoints now use typed request schemas while preserving immutable-field filtering.
- The web workbench provider-config client types now use the same documented provider-type set as the backend.
- Enabled provider configurations are now exclusive per provider type, so creating or re-enabling one provider disables other active configs of the same type and audits the change.
- Implemented typed ticket, log, image, and OCR records that create source material and chunks for retrieval.
- Added EvalRun comparison endpoint and Eval page delta table for comparing consecutive runs.
- ReviewItem to EvalCase conversion now preserves expected source ids, chunk ids, and reviewer-edited answer points for regression coverage.
- Review page now supports editable failure categories and reviewer notes, backed by validated and audited ReviewItem updates.
- Review page now exposes the required reject action through the workbench, backed by audited API rejection.
- Review queue listing now defaults to active work while supporting `status=all` and specific status filters for review history.
- Review-to-FAQ and Review-to-EvalCase conversions now preserve reviewer identity on the ReviewItem and conversion audit event.
- Eval page now surfaces failure-category distribution from EvalRun summary metrics.
- Added a Settings page for creating, editing, deleting, and listing provider configuration records.
- Added ReviewItem detail API/UI that shows the linked question, generated answer, evidence pack, and retrieval trace.
- Enabled LLM provider configs to set answer/model-run identity and estimate model cost in EvalRun summaries.
- Added a credential-gated OpenAI-compatible chat-completions LLM adapter for provider configs named `openai` or `openai_compatible`.
- Unsupported non-fake LLM provider configs now record failed ModelRuns and route generated Answers to Review as generation errors instead of silently using fake execution.
- LLM generation errors and reranker degradation now route to the documented low-confidence-answer review source bucket while preserving actionable failure categories.
- Unsupported non-fake embedding provider configs now fail source ingestion with a saved error reason and source-issue ReviewItem instead of storing fake vectors under a non-fake identity.
- Added a credential-gated OpenAI-compatible embeddings adapter, and vector recall now uses saved chunk embeddings matching the active provider/model instead of re-embedding source chunks during retrieval.
- Unsupported embedding providers are now rejected before chunk insertion, and failed SourceVersions are excluded from retrieval eligibility.
- Added a credential-gated Cohere Rerank adapter that maps indexed Cohere relevance results back onto BoardPilot candidate order.
- Unsupported non-fake reranker provider configs now fall back to merged ranking, mark the RetrievalRun as degraded, and route the Answer to Review as a bad-rerank retrieval issue.
- Unsupported non-fake OCR provider configs now record failed OCR results with error messages and route to Review instead of labeling manual/fake OCR text as configured provider output.
- Added a credential-gated OpenAI-compatible OCR adapter that sends local image assets as Base64 image inputs and ingests returned text through the existing OCR source-version flow.
- OCR providers can now return extracted text directly; provider-returned OCR text is saved as an OcrResult and ingested into a source version/chunks without requiring manual OCR text in the request.
- Added an optional local Tesseract OCR adapter path for private deployments where the `tesseract` executable is installed.
- Image asset OCR result history is now inspectable through an API, including completed and failed provider status.
- Image asset OCR history now treats database-backed ImageAsset rows as authoritative, so empty persisted OCR histories do not leak stale in-memory OCR results.
- Image OCR execution now prefers persisted ImageAsset rows over stale in-memory image metadata before selecting the storage URI to send to the OCR provider.
- Extended enabled provider config identity to saved chunk embeddings, reranked candidate metadata, and OCR results.
- Added explicit source-disable audit logging and a Review action for marking source updates needed.
- Review detail now surfaces Eval failure metrics when a ReviewItem originates from an EvalResult.
- Sources page now inspects source version history, latest-version artifacts, ingestion status, and chunk previews.
- Sources page now shows source-version ingestion error messages and chunk metadata in the detail view.
- Sources page can re-run ingestion for the latest source version through the IngestionJob API.
- Sources page now lists ingestion job history, including queued/completed/failed status, chunk counts, and errors.
- Sources page can import webpage snapshots by URL, store the HTML artifact, and ingest extracted visible text into chunks.
- Sources page can upload image assets to local storage and ingest a manual image description into retrieval chunks.
- Sources page now lists recent ticket, log, image, and OCR import records so support-import source material is inspectable from the workbench.
- Eval page now lists EvalCases and supports editing expected sources/chunks, answer points, tags, difficulty, and active status.
- EvalCase patching now prefers persisted EvalCase rows over stale in-memory EvalCase state before applying edits.
- EvalCase patch, EvalRun creation, and ReviewItem patch endpoints now use typed request schemas instead of raw JSON dictionaries.
- Eval page now shows latest-run per-case results, supports trace inspection with answer/evidence/reranked candidates, and can send failed EvalResults to Review.
- EvalResult to Review conversion now prefers persisted EvalResult records over stale in-memory EvalResult rows before creating review work.
- EvalRun now assigns failure categories for recall, rerank, insufficient-evidence, and unsupported-claim failures so ReviewItems inherit actionable failure reasons.
- EvalRun records now persist the retrieval configuration snapshot and eval duration in the summary metrics for reproducibility.
- EvalRun comparison now prefers persisted EvalRun metric summaries over stale in-memory EvalRun rows before computing deltas.
- Ask-time entity extraction now captures product aliases, firmware versions, error codes, connector names, and hardware interfaces.
- Retrieval tokenization now preserves hardware compound tokens such as error codes and connector/interface names while retaining split subterms.
- Ask page now exposes answer feedback actions for helpful, incorrect, missing-source, and needs-review review routing.
- Ask answer feedback now maps missing-source and incorrect reports to actionable ReviewItem failure categories.
- Helpful Ask feedback is retained in review history without adding open work to the active Review queue.
- Ask answer feedback now rejects missing or unknown feedback types instead of creating ambiguous review work.
- Ask answer feedback now uses a typed request schema so the feedback contract is explicit in the API surface.
- Ask answer feedback now enforces support/reviewer/admin role access so viewer users cannot create review work.
- Ask answer feedback now prefers persisted Answer records over stale in-memory Answer rows before creating review work.
- Ask page now accepts optional metadata filter JSON and sends it with the Ask request.
- Ask metadata filters now constrain retrieval candidates and are recorded in the retrieval filter plan.
- Ask requests now accept optional existing-artifact attachments, persist QuestionAttachment records, return them in the Ask response, and the Ask page has a source/artifact picker for attaching context without raw JSON.
- Ask retrieval now expands the normalized query with attached artifact descriptions and content snippets so log/image/file context can affect retrieval.
- API CORS origins are configurable through `BOARDPILOT_CORS_ORIGINS`, with local Next workbench origins enabled by default.
- Audit logs can optionally be appended to a durable JSONL file through `BOARDPILOT_AUDIT_LOG_PATH`.
- Added a Redis ingestion worker entrypoint and Docker Compose worker service scaffold.
- Source versions can now be disabled with audit logging, which disables their chunks for future retrieval.
- Added a Redis enqueue API path for ingestion jobs with queue message job ids.
- Added runtime QuestionAttachment records and APIs for linking existing artifacts to questions and review detail.
- Review detail now displays linked question attachments for reviewer context.
- Review detail now uses the database-aware review context hydrator so EvalResult metrics and linked retrieval context survive API restarts.
- Sources page can queue the latest source version for the Redis ingestion worker.
- Added a SQLAlchemy catalog repository round-trip for product, source, artifact content, and chunks.
- Added SQLAlchemy runtime repository coverage for ingestion jobs and audit logs.
- Added SQLAlchemy retrieval repository coverage for questions, attachments, retrieval runs, candidates, evidence, model runs, and answers.
- Added SQLAlchemy review/eval/support repository coverage and persisted imported log source content.
- Ingestion job endpoints now mirror job state into the SQLAlchemy runtime repository when the database schema is available.
- Provider configuration APIs now read and mirror provider configs through SQLAlchemy when the database schema is available.
- Provider config deletion now audits the persisted config row instead of stale in-memory config state when both exist.
- Provider-dependent ingestion, Ask, Eval, OCR, review-to-FAQ, and worker paths now hydrate saved provider configs from SQLAlchemy before choosing active providers.
- Audit log writes and reads now mirror through SQLAlchemy when the database schema is available, while keeping JSONL mirroring support.
- Product, product alias, and source catalog endpoints now read and mirror through SQLAlchemy when the database schema is available.
- Product patching now prefers persisted Product rows over stale in-memory Product state before applying edits.
- Source patching and disabling now prefer persisted Source rows over stale in-memory Source state before applying edits.
- Product and source patch endpoints now refresh `updated_at` so mutable catalog records reflect edit time.
- Product, source, and EvalCase patch endpoints now ignore immutable fields such as ids, ownership links, and creation timestamps while still updating approved mutable fields.
- SourceVersion ingestion success, ingestion failure, and disable transitions now refresh `updated_at` so source-version lifecycle state reflects mutation time.
- SourceVersion disable now prefers persisted SourceVersion and Chunk rows over stale in-memory copies before mutating lifecycle state, including empty persisted chunk sets.
- Source disable now refreshes `updated_at`, disables all chunks under the source's versions, and records the disabled chunk count in the audit event; patching a source to disabled follows the same disable semantics.
- Source disable now prefers persisted SourceVersion and Chunk rows over stale in-memory version/chunk state before disabling source chunks, including empty persisted version and chunk sets.
- Source patch, source disable, and source-version disable now use typed request schemas while preserving immutable-field filtering and audit reasons.
- ReviewItem approval, rejection, source-update-needed, FAQ conversion, and EvalCase conversion now refresh `updated_at`.
- Review context hydration now prefers SQLAlchemy records over stale in-memory review, answer, question, retrieval-run, and catalog evidence rows before mutating or converting review work.
- Source version, artifact, chunk, and chunk-embedding endpoints now read and mirror through SQLAlchemy when the database schema is available, preserving empty persisted child lists over stale memory.
- Product child creation paths now prefer persisted Product rows over stale in-memory Product parents before adding aliases, sources, tickets, logs, or images.
- Source version creation and artifact-addition paths now prefer persisted Source and SourceVersion rows over stale in-memory state before parsing and chunking.
- SourceVersion and review-context service hydration now prefer persisted Product, SourceVersion, Source, artifact, chunk, and embedding rows over stale in-memory catalog state before seeding ingestion or review services.
- Child-list endpoints for aliases, source versions, chunks, artifacts, question attachments, retrieval candidates, and eval results now return 404 for missing parent records while preserving empty lists for existing parents with no children.
- Answer evidence listing now treats database-backed Answers and RetrievalRuns as authoritative, so empty persisted evidence sets do not fall back to stale in-memory Evidence rows.
- Review detail now treats database-backed Questions and RetrievalRuns as authoritative for attachments, evidence, and candidates, so empty persisted child lists do not leak stale in-memory trace rows.
- Ask questions, retrieval runs, candidates, evidence, model runs, answers, answer feedback, and question attachments now read and mirror through SQLAlchemy when available.
- Ask attachment hydration now prefers persisted SourceArtifact rows over stale in-memory artifacts before expanding the retrieval query.
- Question attachment creation now prefers persisted Question and SourceArtifact rows over stale in-memory parents before linking the attachment.
- Ask and Eval runs now hydrate products, aliases, sources, source versions, chunks, and chunk embeddings from SQLAlchemy before retrieval so database-backed source material remains retrievable after an API restart.
- Review item queue, detail, update, and decision endpoints now read, hydrate, and mirror through SQLAlchemy when available.
- Eval case, run, comparison, result, and result-to-review endpoints now read and mirror through SQLAlchemy when available.
- EvalRun creation now overwrites stale in-memory EvalCase state with persisted EvalCase rows before running the batch.
- Eval run result persistence now prefers persisted linked ask context over stale in-memory question, retrieval, candidate, evidence, answer, and model-run rows, including empty persisted RetrievalRun child sets.
- Ticket, log source, image asset, and OCR import endpoints now read and mirror through SQLAlchemy when available.
- OCR source-version creation now prefers the persisted Image Source over stale in-memory Source state before chunking OCR text.
- ReviewItem to ApprovedFAQ and ReviewItem to EvalCase conversions now hydrate linked database context and persist generated FAQ/source/eval outputs through SQLAlchemy when available.
- Ingestion job run/enqueue/retry paths now hydrate SourceVersion, Source, Product, Artifact, and existing Chunk context from SQLAlchemy and mirror completed re-ingestion outputs back to SQLAlchemy when available.
- Ingestion job retry now prefers persisted IngestionJob records over stale in-memory job rows before choosing the SourceVersion to reprocess.
- Redis ingestion worker failures now persist source-issue ReviewItems for failed SourceVersions, matching synchronous ingestion failure routing.
- ChunkEmbedding records now read and mirror through SQLAlchemy when available, and embedding persistence is isolated so chunk persistence is not rolled back if embedding storage is unavailable.
- Redis ingestion worker message processing now hydrates job/source context from SQLAlchemy and persists completed job, chunk, and embedding outputs back to SQLAlchemy.

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
headless Chrome screenshots for `/ask`, `/sources`, `/eval`, and `/review`
```

Results:

- API tests: 112 passed.
- Alembic upgrade command: passed against the default local database URL.
- Next.js production build: passed.
- API health: HTTP 200.
- Web routes `/ask`, `/sources`, `/eval`, and `/review`: HTTP 200.
- Headless Chrome visual pass: screenshots captured for `/ask`, `/sources`, `/eval`, and `/review`; each page rendered expected route content with no application-error text detected in the captured HTML.
- Static Docker Compose deployment contract tests: covered by the API test suite.

## Important MVP Gaps

- API runtime persistence is still partly in-memory; SQLAlchemy models, Alembic migrations, and repositories now cover the MVP record groups, Docker startup applies migrations automatically, and product/source/version/ask/review/eval/support-import/provider/job/audit surfaces are database-aware, but parts of the service layer still hydrate the in-memory store before using existing domain services.
- Docker Compose has static contract coverage, but live `docker compose up --build` verification could not be run on this machine because the Docker CLI is not installed.
- IngestionJob APIs and the Redis worker now hydrate source-version context from SQLAlchemy, support retry, enqueue Redis worker messages, and mirror job state plus completed chunk/embedding outputs to SQLAlchemy when available.
- File upload handling exists for parser-aware text sources, PDFs, webpage snapshots, and image assets with manual descriptions; OCR can now use manual text, fake provider behavior, the optional local Tesseract adapter when installed, or OpenAI-compatible vision models.
- Tickets, logs, image manual descriptions, and OCR text now enter the source/chunk pipeline.
- EvalRun can run the required 20-case seed corpus, categorize failed results, inspect per-case traces, send failed cases to Review, and compare numeric metric deltas between two runs.
- Product aliases are detected and saved on Questions; auto-detected products soft-boost retrieval while explicit product selection remains a hard filter.
- High-confidence detected product aliases now become hard product filters while lower-confidence aliases remain soft boosts.
- RetrievalCandidate records now preserve raw keyword/vector recall stages in addition to merged and reranked stages, while Eval Recall@20 remains scoped to the merged recall set.
- Hybrid merge now deduplicates candidates by chunk id, content hash, and near-duplicate source position while preserving deduped chunk ids in candidate metadata.
- Minimal role-aware access control is present for admin, support, maintainer, reviewer, evaluator, and viewer roles; it supports signed session tokens, still preserves header-based local development for MVP, guards Ask feedback mutation, and requires either a configured API key or valid session token across API routes in private deployments.
- Core audit events are inspectable through `GET /audit-logs`; audit writes mirror to SQLAlchemy when available and can still be mirrored to JSONL.
- Answer generation now records provider, model, input hash, prompt version, latency, token estimates, status, and errors in ModelRun records.
- Ask now skips LLM generation when evidence is insufficient, records a skipped ModelRun, and routes the deterministic insufficient-evidence answer to Review.
- Ask now returns an explicit `partial_evidence` answer status when evidence exists but is below the sufficiency threshold, while routing the answer to Review.
- Answer generation now verifies visible citation markers and routes uncited evidence-backed answers to Review as unsupported-claim risks.
- Ingested chunks now store provider/model-specific embedding records for retrieval comparison and re-indexing, with variable provider dimensions supported in new migrations.
- EvalRun summaries now include the MVP-required aggregate metric families, provider config snapshots, and estimated model cost; comparison UI shows numeric deltas between two runs.
- Review approval/rejection/source-update-needed actions now fail without an explicit failure category.
- Review approval, rejection, and source-update-needed actions now use a typed request schema with `FailureCategory` validation at the API boundary.
- Session tokens, bounded token lifetimes, and an operator-managed user/role allowlist are implemented for private deployments, but they are not yet connected to a full identity provider.
- Signed session tokens can now be supplied through either `X-BoardPilot-Session` or standard `Authorization: Bearer` headers.
- Audit logging exists as an in-memory event list, can mirror to JSONL, and now mirrors reads/writes through SQLAlchemy when the schema is available.
- Top-level database-backed list endpoints now treat an existing empty SQL table as authoritative instead of falling back to stale in-memory rows.
- ApprovedFAQ conversion re-ingests reviewer-edited FAQ content into retrieval, EvalCase conversion keeps expected evidence, reviewers can save notes/failure categories, and Review detail shows linked question/answer/evidence/trace/eval metrics.
- The web workbench is functional and has been visually checked with local headless Chrome screenshots for the four primary MVP pages.

## Recommended Next Subtasks

1. Replace the in-memory API store with SQLAlchemy-backed repositories.
2. Add parser-specific PDF extraction, CSV normalization, and image OCR handling for uploaded artifacts.
3. Move ingestion and embedding jobs to Redis-backed workers.
4. Replace header-based local role context with real authentication/session management.
5. Replace failed non-fake provider placeholders with real provider adapters when credentials are configured.
6. Add durable database-backed repositories for runtime data.
