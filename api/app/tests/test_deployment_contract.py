from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def read_repo_file(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_docker_compose_private_stack_contract():
    compose = read_repo_file("docker-compose.yml")

    for service in ("api", "web", "worker", "db", "redis"):
        assert f"  {service}:\n" in compose

    assert "BOARDPILOT_API_HOST: ${BOARDPILOT_API_HOST:-0.0.0.0}" in compose
    assert "BOARDPILOT_API_PORT: ${BOARDPILOT_API_PORT:-8000}" in compose
    assert "BOARDPILOT_DATABASE_URL: ${BOARDPILOT_DATABASE_URL:-postgresql+psycopg://boardpilot:boardpilot@db:5432/boardpilot}" in compose
    assert "BOARDPILOT_REDIS_URL: ${BOARDPILOT_REDIS_URL:-redis://redis:6379/0}" in compose
    assert "BOARDPILOT_API_KEY: ${BOARDPILOT_API_KEY:-}" in compose
    assert "BOARDPILOT_SESSION_TTL_SECONDS: ${BOARDPILOT_SESSION_TTL_SECONDS:-86400}" in compose
    assert "NEXT_PUBLIC_BOARDPILOT_API_KEY: ${NEXT_PUBLIC_BOARDPILOT_API_KEY:-}" in compose
    assert "NEXT_PUBLIC_BOARDPILOT_SESSION_TOKEN: ${NEXT_PUBLIC_BOARDPILOT_SESSION_TOKEN:-}" in compose
    assert "NEXT_PUBLIC_API_BASE_URL: ${NEXT_PUBLIC_API_BASE_URL:-http://localhost:8000}" in compose
    assert "./storage:/app/storage" in compose
    assert "condition: service_healthy" in compose
    assert "pgvector/pgvector:pg16" in compose
    assert "redis:7-alpine" in compose


def test_api_container_runs_migrations_before_serving():
    dockerfile = read_repo_file("api/Dockerfile")

    assert "alembic upgrade head" in dockerfile
    assert "uvicorn app.main:app" in dockerfile
    assert "${BOARDPILOT_API_HOST:-0.0.0.0}" in dockerfile
    assert "${BOARDPILOT_API_PORT:-8000}" in dockerfile


def test_env_example_documents_private_deployment_variables():
    env_example = read_repo_file(".env.example")

    for variable in (
        "BOARDPILOT_ENV=",
        "BOARDPILOT_API_HOST=",
        "BOARDPILOT_API_PORT=",
        "BOARDPILOT_STORAGE_ROOT=",
        "BOARDPILOT_AUDIT_LOG_PATH=",
        "BOARDPILOT_API_KEY=",
        "BOARDPILOT_SESSION_TTL_SECONDS=",
        "BOARDPILOT_CORS_ORIGINS=",
        "BOARDPILOT_DATABASE_URL=",
        "BOARDPILOT_REDIS_URL=",
        "NEXT_PUBLIC_API_BASE_URL=",
        "NEXT_PUBLIC_BOARDPILOT_API_KEY=",
        "NEXT_PUBLIC_BOARDPILOT_SESSION_TOKEN=",
    ):
        assert variable in env_example
