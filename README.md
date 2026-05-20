# BoardPilot

BoardPilot is a private-deployment RAG support workbench for hardware teams. The MVP focuses on proving that source material can be ingested, chunked, retrieved, reranked, cited, reviewed, and measured through an evaluation loop.

## Current MVP Slice

- FastAPI backend with product/source CRUD, ingestion, ask, evidence, answer, review, and eval endpoints.
- Fake LLM, embedding, reranker, and OCR providers so the full loop runs without external credentials.
- In-memory repository for local development and tests.
- Parser-aware ingestion for Markdown, webpage snapshots, CSV/FAQ, logs, uploaded image/manual descriptions, approved FAQs, and PDF text extraction.
- Next.js workbench with Ask, Sources, Eval, and Review pages.
- Docker Compose stack definitions for web, api, worker, Postgres/pgvector, and Redis with health-gated startup.

## Local API

```bash
cd api
python3 -m venv .venv
source .venv/bin/activate
pip install ".[test]"
uvicorn app.main:app --reload --port 8000
```

Run tests:

```bash
cd api
pytest
```

Run migrations:

```bash
cd api
alembic upgrade head
```

## Local Web

```bash
cd web
npm install
npm run dev
```

The web app expects `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`.

## Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

The API container runs Alembic migrations before serving, then the web and worker wait for API health. The current API request path still uses some in-memory service hydration for fast local development, while SQLAlchemy repositories persist the MVP record groups and the Redis worker handles queued ingestion jobs.

Use `.env.example` as the documented deployment template. For private deployments, set `BOARDPILOT_API_KEY` and either mirror the same value to `NEXT_PUBLIC_BOARDPILOT_API_KEY` or issue a signed role-bound token with `POST /sessions` and provide it as `NEXT_PUBLIC_BOARDPILOT_SESSION_TOKEN` for the bundled workbench. `BOARDPILOT_API_HOST` and `BOARDPILOT_API_PORT` control the API bind address inside the container.
