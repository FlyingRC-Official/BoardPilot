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

The API container runs `alembic upgrade head` before starting Uvicorn. Postgres and Redis have health checks, and the web and worker services wait for the API health endpoint, so a fresh private stack can bootstrap its schema from an empty database volume.

The `.env.example` file documents the required private-deployment variables. `BOARDPILOT_API_HOST` and `BOARDPILOT_API_PORT` control the API bind address inside the container, while `NEXT_PUBLIC_API_BASE_URL` controls where the browser workbench sends API requests.

## Privacy Boundary

The default provider config is fake/local. Source content should not leave the deployment unless an admin intentionally enables an external LLM, embedding, reranker, or OCR provider.

LLM provider configs support an OpenAI-compatible chat-completions adapter by setting `provider_name` to `openai` or `openai_compatible`. Embedding provider configs support the same provider names through the OpenAI-compatible embeddings endpoint. Use `config_json` such as `{"api_key_env":"OPENAI_API_KEY","base_url":"https://api.openai.com/v1"}` so credentials stay in environment variables instead of stored provider records.

## API Key Gate

Local development leaves `BOARDPILOT_API_KEY` empty, so the workbench can use the role headers directly. In a private deployment, set `BOARDPILOT_API_KEY` for the API and worker, and set the same value as `NEXT_PUBLIC_BOARDPILOT_API_KEY` for the bundled private web workbench so browser requests include `X-BoardPilot-API-Key`.

Admins can also mint signed session tokens with `POST /sessions` while authenticated with the deployment API key. Session requests use `X-BoardPilot-Session` and carry a fixed user id, role, and expiry time, so private deployments do not need to expose the deployment API key to every browser request. `BOARDPILOT_SESSION_TTL_SECONDS` controls the default token lifetime, and the bundled workbench can receive a token through `NEXT_PUBLIC_BOARDPILOT_SESSION_TOKEN`.

Set `BOARDPILOT_USERS_JSON` to an object such as `{"alice":"admin","support-1":"support"}` to make session issuance check an operator-managed allowlist. When this setting is present, `POST /sessions` rejects any requested user id and role that do not exactly match the configured map.

## MVP Gaps

The current implementation is a runnable development slice. Before production use, replace remaining in-memory service hydration, connect session issuance to a full identity provider if needed, and enforce durable audit retention.
