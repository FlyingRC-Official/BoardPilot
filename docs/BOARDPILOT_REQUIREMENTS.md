# BoardPilot MVP Requirements Document

## 1. Project Overview

BoardPilot is a private-deployment RAG support assistant for hardware teams.

The first MVP is not optimized for having the largest language model. Its core goal is to prove that the right source material can be consistently retrieved, reranked, cited, reviewed, and improved through an evaluation loop.

The product is a web workbench with four primary pages:

- Ask
- Sources
- Eval
- Review

The key success criterion is:

> For real hardware support questions, the correct source chunks should enter the reranked Top 5, and candidate answers should be generated only from saved evidence ids with visible citations.

## 2. Goals and Non-Goals

### 2.1 Goals

- Provide a private RAG assistant for hardware support teams.
- Support ingestion of hardware manuals, PDFs, Markdown docs, webpages, CSV/FAQ files, historical tickets, text logs, and image OCR/manual descriptions.
- Store all source versions, chunks, retrieval runs, evidence, generated answers, eval results, and review decisions.
- Use hybrid retrieval: full-text search, vector search, metadata filters, merge/dedup, rerank.
- Generate citation-backed candidate answers.
- Route low-confidence or insufficient-evidence answers to human review.
- Convert approved human-reviewed answers into FAQ sources.
- Convert reviewed failures into EvalCases.
- Provide a measurable optimization loop through Eval metrics.
- Support local/private deployment through Docker Compose.
- Use provider abstractions for LLM, embedding, reranker, and OCR providers.

### 2.2 Non-Goals for MVP

- Do not build a public SaaS multi-tenant billing system in MVP.
- Do not implement complex autonomous agents.
- Do not require cloud storage in the first version.
- Do not optimize for open-ended chat history before retrieval quality is measurable.
- Do not treat generated answers as authoritative unless they are backed by saved evidence ids.

## 3. Users and Roles

### 3.1 Admin

Responsibilities:

- Configure products.
- Configure model providers.
- Upload and manage sources.
- Manage private deployment settings.
- Review audit logs.

### 3.2 Support Engineer

Responsibilities:

- Ask product support questions.
- Inspect evidence and citations.
- Review low-confidence answers.
- Approve, edit, or reject generated answers.
- Convert reviewed answers into FAQs or EvalCases.

### 3.3 Knowledge Maintainer

Responsibilities:

- Upload and version source materials.
- Correct bad or outdated sources.
- Maintain product aliases and metadata.
- Inspect failed retrieval cases.

### 3.4 Evaluator

Responsibilities:

- Create EvalCases.
- Mark expected source/chunk evidence.
- Run Eval batches.
- Analyze failure categories.

## 4. Product Pages

### 4.1 Ask Page

Purpose:

- Let users ask hardware support questions and inspect citation-backed candidate answers.

Core features:

- Input question text.
- Optional product selector.
- Optional metadata filters.
- Optional file/image/log attachment.
- Display candidate answer.
- Display evidence pack.
- Display citation links.
- Display evidence sufficiency status.
- Display simplified retrieval trace.
- Allow user feedback: helpful, incorrect, missing source, needs review.

Required states:

- Idle
- Running retrieval
- Generating answer
- Sufficient evidence
- Partial evidence
- Insufficient evidence
- Failed

Acceptance criteria:

- A submitted question creates a Question record.
- Every Ask request creates a RetrievalRun.
- Every generated answer must link to saved Evidence records.
- If evidence is partial or insufficient, a ReviewItem is created.
- The user can inspect which source chunks were used.

### 4.2 Sources Page

Purpose:

- Manage source materials and ingestion status.

Core features:

- Create product.
- Create source.
- Upload source version artifacts.
- Support file types:
  - PDF
  - Markdown
  - webpage snapshot or URL import
  - CSV/FAQ
  - text logs
  - historical ticket exports
  - images with OCR or manual explanation
- Show source version history.
- Show ingestion status.
- Show parsed artifacts.
- Show chunk preview.
- Show chunk metadata.
- Allow re-ingestion.

Acceptance criteria:

- Uploading a supported source creates SourceVersion and SourceArtifact records.
- Ingestion creates Chunk records.
- Duplicate chunks are detected by content hash.
- Failed ingestion saves an error reason.
- Previous source versions remain queryable unless explicitly disabled.

### 4.3 Eval Page

Purpose:

- Measure whether retrieval, reranking, evidence selection, and answer generation are improving.

Core features:

- Create EvalCase.
- Edit EvalCase.
- Mark expected sources/chunks.
- Run EvalRun.
- Compare EvalRuns.
- Show per-case trace.
- Show aggregate metrics.
- Convert failed EvalCase result to ReviewItem.

Required metrics:

- Recall@20
- Rerank@5
- Citation Support Rate
- Unsupported Claim Rate
- Need Review Rate
- Evidence Sufficiency Rate
- Failure Category distribution
- Latency
- Model cost where available

Acceptance criteria:

- A batch EvalRun can run against at least 20 seed EvalCases.
- Each EvalResult stores retrieval candidates, evidence, answer id, and metric results.
- Failures can be categorized and sent to Review.

### 4.4 Review Page

Purpose:

- Provide a human review loop for low-confidence answers, eval failures, and user-reported issues.

Core features:

- Review queue.
- Review item detail.
- Show original question.
- Show generated answer.
- Show evidence pack.
- Show retrieval trace.
- Allow reviewer to edit answer.
- Require failure category before approval or rejection.
- Approve answer.
- Reject answer.
- Mark source update needed.
- Convert to ApprovedFAQ.
- Convert to EvalCase.

Failure categories:

- missing_source
- stale_source
- bad_parse
- bad_chunk
- bad_query_normalization
- bad_metadata_filter
- bad_keyword_recall
- bad_vector_recall
- bad_merge_dedup
- bad_rerank
- insufficient_evidence
- unsupported_claim
- generation_error
- product_alias_missing
- human_policy_required

Acceptance criteria:

- Low-confidence answers enter the review queue.
- Reviewers cannot approve without a failure category when the answer was problematic.
- Approved answers can become ApprovedFAQ records.
- Review items can become EvalCases.
- Review decisions are audit logged.

## 5. System Architecture

### 5.1 Recommended MVP Architecture

Use a modular monolith:

- Frontend: Next.js + React
- Backend: FastAPI
- Database: Postgres + pgvector
- File storage: local filesystem through a StorageProvider abstraction
- Worker: async task process using Redis-backed queue
- Provider layer: interchangeable LLM, embedding, reranker, OCR providers
- Deployment: Docker Compose

Do not split into microservices for MVP. The system should be deployed as a small private stack with clear module boundaries.

### 5.2 Backend Modules

Required modules:

- core
- db
- models
- products
- sources
- ingestion
- storage
- providers
- retrieval
- answers
- eval
- review
- tickets
- logs
- images
- workers
- audit

### 5.3 Frontend Modules

Required modules:

- app/ask
- app/sources
- app/eval
- app/review
- components/navigation
- components/evidence
- components/source-viewer
- components/retrieval-trace
- components/review-editor
- lib/api-client
- lib/types

## 6. Data Model Requirements

### 6.1 Product

Represents a hardware product, board, module, accessory, or product family.

Fields:

- id
- name
- slug
- description
- status
- created_at
- updated_at

Relationships:

- has many ProductAlias
- has many Sources
- has many Questions
- has many EvalCases

### 6.2 ProductAlias

Represents alternate names, model numbers, typos, internal names, and user-facing names.

Fields:

- id
- product_id
- alias
- alias_type
- confidence
- created_at

Why:

Hardware support questions often use inconsistent product names. Alias handling improves recall and prevents overly strict metadata filtering.

### 6.3 Source

Logical knowledge source, such as a manual, FAQ collection, webpage, ticket export, or log corpus.

Fields:

- id
- product_id
- title
- source_type
- canonical_uri
- status
- trust_level
- created_at
- updated_at

Source types:

- pdf
- markdown
- webpage
- csv_faq
- ticket_export
- text_log
- image
- approved_faq
- manual_note

### 6.4 SourceVersion

Versioned instance of a Source.

Fields:

- id
- source_id
- version_label
- content_hash
- status
- effective_from
- effective_to
- parser_version
- created_at
- updated_at

Why:

Hardware documentation changes over time. Retrieval and citations must be traceable to the exact source version used.

### 6.5 SourceArtifact

Physical or derived artifact associated with a SourceVersion.

Fields:

- id
- source_version_id
- artifact_type
- storage_uri
- mime_type
- size_bytes
- checksum
- metadata_json
- created_at

Artifact types:

- original
- extracted_text
- normalized_markdown
- ocr_text
- webpage_snapshot
- parser_debug

### 6.6 Chunk

Searchable text unit.

Fields:

- id
- source_version_id
- product_id
- chunk_index
- title_path
- content
- content_hash
- token_count
- char_start
- char_end
- page_number
- section_name
- metadata_json
- enabled
- created_at

Requirements:

- Must preserve source position where possible.
- Must support deduplication by content hash.
- Must be stable enough to use in EvalCase expected evidence.

### 6.7 ChunkEmbedding

Embedding vector for a chunk under a specific model.

Fields:

- id
- chunk_id
- provider_name
- model_name
- embedding_dimension
- vector
- created_at

Why:

Embedding models may change. Keeping model-specific embeddings allows comparison and re-indexing.

### 6.8 Question

Represents a user-submitted support question.

Fields:

- id
- product_id
- raw_text
- normalized_text
- detected_entities_json
- metadata_filters_json
- user_id
- created_at

### 6.9 QuestionAttachment

Represents optional attached files, images, logs, or screenshots.

Fields:

- id
- question_id
- artifact_id
- attachment_type
- description
- created_at

### 6.10 RetrievalRun

Represents one execution of the retrieval pipeline.

Fields:

- id
- question_id
- retrieval_config_json
- normalized_query
- filter_plan_json
- status
- started_at
- completed_at
- latency_ms
- error_message

Why:

RetrievalRun is a core product object, not just logs. It enables debugging, Eval, and Review.

### 6.11 RetrievalCandidate

Candidate chunk produced during retrieval.

Fields:

- id
- retrieval_run_id
- chunk_id
- stage
- source
- keyword_score
- vector_score
- merged_score
- rerank_score
- rank
- metadata_json

Stages:

- keyword
- vector
- merged
- reranked

### 6.12 Evidence

Final evidence selected for answer generation.

Fields:

- id
- retrieval_run_id
- chunk_id
- rank
- score
- quote
- selection_reason
- created_at

Requirements:

- Every generated answer citation must reference Evidence ids.
- Evidence must point to exact chunks and preferably source positions.

### 6.13 Answer

Candidate answer generated from evidence.

Fields:

- id
- question_id
- retrieval_run_id
- status
- answer_text
- citation_map_json
- evidence_sufficiency
- confidence
- provider_name
- model_name
- prompt_version
- model_run_id
- created_at

Evidence sufficiency values:

- sufficient
- partial
- insufficient

### 6.14 EvalCase

Regression test case for retrieval and answer quality.

Fields:

- id
- product_id
- question_text
- expected_source_ids_json
- expected_chunk_ids_json
- expected_answer_points_json
- tags_json
- difficulty
- active
- created_at
- updated_at

### 6.15 EvalRun

Batch run of EvalCases.

Fields:

- id
- name
- retrieval_config_json
- provider_config_json
- status
- started_at
- completed_at
- summary_metrics_json

### 6.16 EvalResult

Per-case evaluation result.

Fields:

- id
- eval_run_id
- eval_case_id
- question_id
- retrieval_run_id
- answer_id
- recall_at_20
- rerank_at_5
- citation_support_rate
- unsupported_claim_rate
- need_review
- failure_category
- metrics_json
- created_at

### 6.17 ReviewItem

Human review unit.

Fields:

- id
- source_type
- question_id
- answer_id
- eval_result_id
- status
- priority
- failure_category
- reviewer_id
- reviewer_notes
- edited_answer_text
- created_at
- updated_at

Source types:

- low_confidence_answer
- insufficient_evidence
- user_feedback
- eval_failure
- source_issue

Statuses:

- open
- in_review
- approved
- rejected
- needs_source_update
- converted_to_faq
- converted_to_eval_case

### 6.18 ApprovedFAQ

Human-approved FAQ generated from review.

Fields:

- id
- product_id
- review_item_id
- question_text
- answer_text
- source_id
- status
- created_at
- updated_at

Requirement:

- ApprovedFAQ must be re-ingested as source material so it can enter retrieval.

### 6.19 Ticket

Historical or live support ticket.

Fields:

- id
- product_id
- external_id
- title
- body
- status
- tags_json
- anonymized
- source_id
- created_at

### 6.20 LogSource

Text or device log source.

Fields:

- id
- product_id
- source_id
- log_type
- device_context_json
- time_range_json
- created_at

### 6.21 ImageAsset

Image, screenshot, diagram, or photo source.

Fields:

- id
- product_id
- source_id
- storage_uri
- image_type
- manual_description
- created_at

### 6.22 OcrResult

OCR result for image sources.

Fields:

- id
- image_asset_id
- provider_name
- model_name
- ocr_text
- confidence
- created_at

### 6.23 ProviderConfig

Configuration for LLM, embedding, reranker, or OCR provider.

Fields:

- id
- provider_type
- provider_name
- model_name
- config_json
- enabled
- created_at

### 6.24 ModelRun

Trace for each model invocation.

Fields:

- id
- provider_type
- provider_name
- model_name
- input_hash
- prompt_version
- latency_ms
- token_usage_json
- cost_json
- status
- error_message
- created_at

### 6.25 AuditLog

Records sensitive changes and review decisions.

Fields:

- id
- user_id
- action
- entity_type
- entity_id
- before_json
- after_json
- created_at

## 7. Retrieval Pipeline Requirements

### 7.1 Pipeline

The retrieval pipeline must follow this sequence:

1. Question intake
2. Product and entity extraction
3. Query normalization
4. Filter plan generation
5. Keyword recall
6. Vector recall
7. Merge and dedup
8. Rerank
9. Evidence pack creation
10. Evidence sufficiency check
11. Citation answer generation
12. Citation verification
13. Review routing

### 7.2 Product and Entity Extraction

Purpose:

- Detect product names, board names, connector names, firmware versions, error codes, and hardware interfaces.

Requirements:

- Use ProductAlias table for product detection.
- Do not apply strict product filtering unless confidence is high or the user explicitly selected a product.
- Save detected entities in Question.detected_entities_json.

### 7.3 Query Normalization

Requirements:

- Preserve original user wording.
- Create normalized query for retrieval.
- Expand known aliases.
- Keep hardware-specific tokens such as part numbers, connector names, model numbers, and error codes.

### 7.4 Filter Plan

Filter types:

- hard_filter
- soft_boost

Rules:

- User-selected product can be a hard filter.
- Auto-detected product should usually be a soft boost unless confidence is high.
- Source type filters should be optional.
- Disabled chunks must never be retrieved.

### 7.5 Hybrid Recall

Keyword recall:

- Use Postgres full-text search.
- Favor exact matches on model numbers, parameter names, connector names, and error codes.

Vector recall:

- Use pgvector.
- Embedding model must be configurable.

Initial recall target:

- Top 30-50 candidates before rerank.

### 7.6 Merge and Dedup

Requirements:

- Merge keyword and vector candidates.
- Deduplicate by chunk id, content hash, and near-duplicate source position.
- Preserve original keyword and vector scores.
- Save merged candidates.

### 7.7 Rerank

Requirements:

- Rerank merged candidates.
- Save rerank score and rank.
- Select Top 5-8 for evidence pack.
- Reranker must be behind provider abstraction.

### 7.8 Evidence Pack

Requirements:

- Evidence pack contains selected chunks, quotes, ranks, scores, and selection reasons.
- Evidence must be saved before answer generation.
- Answers may only cite saved Evidence ids.

### 7.9 Evidence Sufficiency Check

Output values:

- sufficient
- partial
- insufficient

Rules:

- If evidence is insufficient, do not produce a confident answer.
- Partial or insufficient evidence should create ReviewItem.

### 7.10 Citation Answer

Requirements:

- Answer text must include citation references.
- Citation map must link answer claims to Evidence ids.
- Unsupported claims should be minimized and measurable.
- Prompt and model run metadata must be saved.

### 7.11 Citation Verification

Requirements:

- Verify that each major answer claim is supported by at least one Evidence id.
- Unsupported claim rate must be stored when evaluator is available.
- High unsupported claim risk should route to Review.

## 8. Eval Requirements

### 8.1 EvalCase Design

Each EvalCase should include:

- Question text.
- Product.
- Expected source ids.
- Expected chunk ids where available.
- Expected answer points.
- Tags.
- Difficulty.

Tags examples:

- setup
- wiring
- firmware
- hardware_fault
- compatibility
- parameter
- log_analysis
- image_based
- ticket_regression

### 8.2 Metrics

Required metrics:

- Recall@20
- Rerank@5
- Citation Support Rate
- Unsupported Claim Rate
- Need Review Rate
- Evidence Sufficiency Rate
- Failure Category distribution
- Latency p50/p95

### 8.3 Failure Analysis

Every failed EvalResult should support a failure category.

Failure category is required to drive system improvement. Without it, Eval only reports that the system is bad, not why it is bad.

### 8.4 Eval Acceptance Criteria

- EvalRun can run against a fixed test set.
- EvalRun results are reproducible with the same provider config.
- EvalRun stores retrieval and answer traces.
- Failed EvalResults can become ReviewItems.

## 9. Review Loop Requirements

### 9.1 Review Sources

ReviewItems can be created from:

- low-confidence Ask answer
- insufficient evidence
- user feedback
- Eval failure
- source parsing issue
- missing source issue

### 9.2 Review Actions

Supported actions:

- approve
- reject
- edit answer
- mark source update needed
- convert to ApprovedFAQ
- convert to EvalCase

### 9.3 ApprovedFAQ Flow

Flow:

1. Reviewer approves or edits an answer.
2. Reviewer converts it to ApprovedFAQ.
3. System creates or updates an FAQ Source.
4. FAQ SourceVersion is ingested.
5. New FAQ chunks are embedded.
6. Future retrieval can hit the approved FAQ.

### 9.4 EvalCase Flow

Flow:

1. Reviewer identifies a useful regression case.
2. Reviewer converts ReviewItem to EvalCase.
3. Expected evidence and answer points are saved.
4. Future EvalRuns include the new case.

## 10. API Requirements

### 10.1 Health and Metadata

```text
GET /health
GET /version
GET /providers
```

### 10.2 Product APIs

```text
POST /products
GET /products
GET /products/{id}
PATCH /products/{id}
POST /products/{id}/aliases
GET /products/{id}/aliases
```

### 10.3 Source APIs

```text
POST /sources
GET /sources
GET /sources/{id}
PATCH /sources/{id}
POST /sources/{source_id}/versions
GET /sources/{source_id}/versions
POST /sources/{source_id}/versions/{version_id}/artifacts
GET /source-versions/{version_id}/chunks
```

### 10.4 Ingestion APIs

```text
POST /ingestion/jobs
GET /ingestion/jobs
GET /ingestion/jobs/{id}
POST /ingestion/jobs/{id}/retry
```

### 10.5 Ask and Retrieval APIs

```text
POST /ask
GET /questions/{id}
GET /retrieval-runs/{id}
GET /retrieval-runs/{id}/candidates
GET /answers/{id}
GET /answers/{id}/evidence
POST /answers/{id}/feedback
```

### 10.6 Eval APIs

```text
POST /eval-cases
GET /eval-cases
GET /eval-cases/{id}
PATCH /eval-cases/{id}
POST /eval-runs
GET /eval-runs
GET /eval-runs/{id}
GET /eval-runs/{id}/results
POST /eval-results/{id}/to-review
```

### 10.7 Review APIs

```text
GET /review-items
GET /review-items/{id}
PATCH /review-items/{id}
POST /review-items/{id}/approve
POST /review-items/{id}/reject
POST /review-items/{id}/to-faq
POST /review-items/{id}/to-eval-case
```

### 10.8 Ticket, Log, and Image APIs

```text
POST /tickets
GET /tickets
POST /log-sources
GET /log-sources
POST /image-assets
GET /image-assets
POST /image-assets/{id}/ocr
```

## 11. Provider Abstraction Requirements

### 11.1 Provider Types

Required provider interfaces:

- LLMProvider
- EmbeddingProvider
- RerankerProvider
- OCRProvider

### 11.2 MVP Providers

The MVP must include:

- FakeLLMProvider
- FakeEmbeddingProvider
- FakeRerankerProvider
- FakeOCRProvider

Why:

Fake providers allow Codex, CI, and local development to verify the full pipeline without relying on external model credentials.

### 11.3 Provider Interface Requirements

All providers must return:

- structured result
- provider name
- model name
- latency
- error message if failed
- model run record where applicable

## 12. Security and Private Deployment

### 12.1 Private Deployment Requirements

- Docker Compose deployment.
- Local file storage by default.
- Environment variable based configuration.
- No source content should leave the deployment unless configured through provider settings.
- `.env.example` must document required configuration.

### 12.2 Access Control

MVP should include simple role-aware user structure even if authentication starts minimal.

Required roles:

- admin
- support
- reviewer
- viewer

### 12.3 Audit Logging

Audit log required for:

- source deletion or disabling
- provider config change
- review approval or rejection
- ApprovedFAQ creation
- EvalCase modification

## 13. Codex-Friendly Development Plan

### 13.1 Week 1: Project Skeleton and Data Foundation

Goal:

- Establish runnable private development stack and core schema.

Create or edit:

- `docker-compose.yml`
- `README.md`
- `api/app/main.py`
- `api/app/core/config.py`
- `api/app/db/session.py`
- `api/app/db/base.py`
- `api/app/models/`
- `api/alembic/`
- `web/app/layout.tsx`
- `web/app/ask/page.tsx`
- `web/app/sources/page.tsx`
- `web/app/eval/page.tsx`
- `web/app/review/page.tsx`

Database:

- products
- product_aliases
- sources
- source_versions
- source_artifacts
- chunks

Tests:

- health endpoint test
- migration test
- Product CRUD test
- Source CRUD test
- Docker Compose smoke test

Acceptance criteria:

- `docker compose up` starts web, api, db, and redis.
- Four web pages are reachable.
- Product and Source can be created.
- Migrations run from an empty database.

### 13.2 Week 2: Sources and Ingestion

Goal:

- Convert uploaded source materials into versioned, deduplicated chunks.

Create or edit:

- `api/app/storage/base.py`
- `api/app/storage/local.py`
- `api/app/ingestion/jobs.py`
- `api/app/ingestion/tasks.py`
- `api/app/ingestion/chunking.py`
- `api/app/ingestion/parsers/markdown.py`
- `api/app/ingestion/parsers/csv_faq.py`
- `api/app/ingestion/parsers/text_log.py`
- `api/app/ingestion/parsers/pdf.py`
- `api/app/ingestion/parsers/image_stub.py`
- `web/app/sources/page.tsx`

Database:

- ingestion_jobs
- add ingestion status fields to source_versions
- add artifact metadata fields

Tests:

- parser tests
- chunking tests
- dedup tests
- ingestion job status tests

Acceptance criteria:

- Markdown, CSV, TXT/log, and PDF text extraction generate chunks.
- Image sources can be stored with manual description or OCR placeholder.
- Duplicate chunks are not repeatedly created.
- Ingestion failures are visible and recoverable.

### 13.3 Week 3: Providers and Retrieval

Goal:

- Implement provider abstractions and hybrid retrieval with rerank.

Create or edit:

- `api/app/providers/base.py`
- `api/app/providers/fake.py`
- `api/app/providers/embedding.py`
- `api/app/providers/reranker.py`
- `api/app/providers/llm.py`
- `api/app/providers/ocr.py`
- `api/app/retrieval/query_normalization.py`
- `api/app/retrieval/filter_plan.py`
- `api/app/retrieval/keyword.py`
- `api/app/retrieval/vector.py`
- `api/app/retrieval/merge.py`
- `api/app/retrieval/rerank.py`
- `api/app/retrieval/service.py`

Database:

- provider_configs
- model_runs
- chunk_embeddings
- questions
- retrieval_runs
- retrieval_candidates

Tests:

- fake provider tests
- embedding job test
- keyword search test
- vector search test
- merge/dedup test
- rerank test
- retrieval run persistence test

Acceptance criteria:

- Retrieval can return merged and reranked Top 5 candidates.
- Keyword, vector, merged, and reranked stages are saved.
- Fake providers allow full local pipeline execution.

### 13.4 Week 4: Ask, Evidence, and Answers

Goal:

- Complete user question to citation-backed candidate answer loop.

Create or edit:

- `api/app/answers/service.py`
- `api/app/answers/citation.py`
- `api/app/answers/sufficiency.py`
- `api/app/retrieval/evidence.py`
- `api/app/review/routing.py`
- `web/app/ask/page.tsx`
- `web/components/evidence/`
- `web/components/retrieval-trace/`

Database:

- evidences
- answers
- review_items
- question_attachments

Tests:

- ask integration test
- evidence pack test
- answer citation map test
- answer cannot cite non-evidence test
- insufficient evidence routes to review test

Acceptance criteria:

- Ask page returns a candidate answer with citations.
- Every citation maps to Evidence ids.
- Evidence points back to SourceVersion and Chunk.
- Partial or insufficient evidence creates ReviewItem.

### 13.5 Week 5: Eval

Goal:

- Build measurable evaluation loop for retrieval and answer quality.

Create or edit:

- `api/app/eval/cases.py`
- `api/app/eval/runs.py`
- `api/app/eval/metrics.py`
- `api/app/eval/failure_categories.py`
- `web/app/eval/page.tsx`
- `web/components/eval/`

Database:

- eval_cases
- eval_runs
- eval_results

Tests:

- Recall@20 test
- Rerank@5 test
- Citation Support Rate test
- Unsupported Claim Rate stub test
- EvalRun persistence test
- failed EvalResult to ReviewItem test

Acceptance criteria:

- At least 20 seed EvalCases can run as a batch.
- EvalRun shows aggregate metrics.
- Per-case traces are inspectable.
- Failed cases can be sent to Review.

### 13.6 Week 6: Review Loop, FAQ Feedback, and Private MVP

Goal:

- Complete Review loop and private deployment readiness.

Create or edit:

- `api/app/review/service.py`
- `api/app/review/actions.py`
- `api/app/approved_faqs/`
- `api/app/tickets/`
- `api/app/logs/`
- `api/app/images/`
- `api/app/audit/`
- `web/app/review/page.tsx`
- `.env.example`
- `docs/DEPLOYMENT.md`
- `docs/EVAL_GUIDE.md`

Database:

- approved_faqs
- tickets
- log_sources
- image_assets
- ocr_results
- audit_logs

Tests:

- review approval test
- failure category required test
- review to FAQ test
- FAQ re-ingestion test
- review to EvalCase test
- private deployment smoke test

Acceptance criteria:

- Review queue works end to end.
- ApprovedFAQ can be re-ingested and retrieved.
- ReviewItem can become EvalCase.
- Tickets, logs, and image-derived text can enter the source pipeline.
- Docker Compose private deployment is documented and repeatable.

## 14. Recommended Repository Structure

```text
BoardPilot/
  README.md
  docker-compose.yml
  .env.example
  api/
    pyproject.toml
    alembic.ini
    alembic/
    app/
      main.py
      core/
      db/
      models/
      products/
      sources/
      ingestion/
      storage/
      providers/
      retrieval/
      answers/
      eval/
      review/
      approved_faqs/
      tickets/
      logs/
      images/
      audit/
      workers/
      tests/
  web/
    package.json
    next.config.js
    app/
      ask/
      sources/
      eval/
      review/
    components/
      evidence/
      source-viewer/
      retrieval-trace/
      review-editor/
      eval/
    lib/
      api-client.ts
      types.ts
  packages/
    schemas/
  storage/
    originals/
    derived/
  docs/
    BOARDPILOT_REQUIREMENTS.md
    DEPLOYMENT.md
    EVAL_GUIDE.md
```

## 15. Final MVP Acceptance Criteria

The MVP is accepted when all of the following are true:

- A private Docker Compose deployment starts successfully.
- Users can manage products and product aliases.
- Users can upload source materials.
- PDF, Markdown, CSV/FAQ, text logs, tickets, and image-derived text can become chunks.
- Chunks can be embedded.
- Ask executes hybrid retrieval and rerank.
- Correct source chunks can be measured entering reranked Top 5.
- Candidate answers include citations mapped to saved Evidence ids.
- Insufficient or risky answers enter Review.
- Reviewers can approve, edit, reject, convert to FAQ, and convert to EvalCase.
- ApprovedFAQ content re-enters retrieval.
- EvalRun measures Recall@20, Rerank@5, Citation Support Rate, Unsupported Claim Rate, Need Review Rate, and Failure Category distribution.
- Core operations are audit logged.

## 16. Human Review Boundaries

Codex can implement:

- Repo scaffold.
- FastAPI modules.
- Next.js pages.
- Database models and migrations.
- Fake providers.
- Parser stubs and basic parsers.
- Retrieval pipeline.
- Eval metrics.
- Review workflow.
- Tests and seed data.

Humans must review:

- Product taxonomy and aliases.
- Source trust level.
- Outdated or conflicting documentation.
- Gold evidence for EvalCases.
- Approved support answers.
- Failure category calibration.
- Privacy handling for tickets, logs, and images.
- Customer-facing FAQ wording.

