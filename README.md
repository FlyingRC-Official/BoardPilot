# BoardPilot

BoardPilot is a private-deployment RAG support workbench for hardware teams. The MVP focuses on proving that source material can be ingested, chunked, retrieved, reranked, cited, reviewed, and measured through an evaluation loop.

## Current MVP Slice

- FastAPI backend with product/source CRUD, ingestion, ask, evidence, answer, review, and eval endpoints.
- Fake LLM, embedding, reranker, and OCR providers so the full loop runs without external credentials.
- In-memory repository for local development and tests.
- Next.js workbench with Ask, Sources, Eval, and Review pages.
- Docker Compose stack definitions for web, api, Postgres, and Redis.

## Local API

```bash
cd api
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"
uvicorn app.main:app --reload --port 8000
```

Run tests:

```bash
cd api
pytest
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

The current API uses in-memory storage. Postgres, pgvector, Redis workers, durable file metadata, and migrations are scaffolded for the private stack but still need production implementation.

