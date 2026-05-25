from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[3]


def read_repo_file(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_docker_compose_private_stack_contract():
    compose = read_repo_file("docker-compose.yml")

    for service in ("api", "web", "worker", "db", "redis"):
        assert f"  {service}:\n" in compose

    assert "BOARDPILOT_API_HOST: ${BOARDPILOT_API_HOST:-0.0.0.0}" in compose
    assert "BOARDPILOT_API_PORT: ${BOARDPILOT_API_PORT:-8000}" in compose
    assert '"${BOARDPILOT_API_HOST_PORT:-8000}:${BOARDPILOT_API_PORT:-8000}"' in compose
    assert '"${BOARDPILOT_WEB_HOST_PORT:-3000}:3000"' in compose
    assert "BOARDPILOT_DATABASE_URL: ${BOARDPILOT_DATABASE_URL:-postgresql+psycopg://boardpilot:boardpilot@db:5432/boardpilot}" in compose
    assert "BOARDPILOT_REDIS_URL: ${BOARDPILOT_REDIS_URL:-redis://redis:6379/0}" in compose
    assert "BOARDPILOT_API_KEY: ${BOARDPILOT_API_KEY:-}" in compose
    assert "BOARDPILOT_SESSION_TTL_SECONDS: ${BOARDPILOT_SESSION_TTL_SECONDS:-86400}" in compose
    assert "BOARDPILOT_USERS_JSON: ${BOARDPILOT_USERS_JSON:-}" in compose
    assert "PIP_INDEX_URL: ${PIP_INDEX_URL:-}" in compose
    assert "PIP_EXTRA_INDEX_URL: ${PIP_EXTRA_INDEX_URL:-}" in compose
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
    assert "ARG PIP_INDEX_URL" in dockerfile
    assert "ARG PIP_EXTRA_INDEX_URL" in dockerfile
    assert "PIP_DEFAULT_TIMEOUT=120" in dockerfile


def test_alembic_revision_ids_fit_postgres_version_table():
    version_dir = REPO_ROOT / "api" / "alembic" / "versions"
    revision_pattern = re.compile(r'^revision = "([^"]+)"$', re.MULTILINE)
    down_revision_pattern = re.compile(r'^down_revision = "([^"]+)"$', re.MULTILINE)
    revisions: set[str] = set()
    down_revisions: set[str] = set()

    for migration in version_dir.glob("*.py"):
        text = migration.read_text(encoding="utf-8")
        revision_match = revision_pattern.search(text)
        assert revision_match is not None, f"{migration.name} is missing revision"
        revision = revision_match.group(1)
        assert len(revision) <= 32, f"{migration.name} revision is too long for Alembic's Postgres version table"
        revisions.add(revision)

        down_revision_match = down_revision_pattern.search(text)
        if down_revision_match is not None:
            down_revisions.add(down_revision_match.group(1))

    assert down_revisions - {None, "None"} <= revisions


def test_env_example_documents_private_deployment_variables():
    env_example = read_repo_file(".env.example")

    for variable in (
        "BOARDPILOT_ENV=",
        "BOARDPILOT_API_HOST=",
        "BOARDPILOT_API_PORT=",
        "BOARDPILOT_API_HOST_PORT=",
        "BOARDPILOT_WEB_HOST_PORT=",
        "BOARDPILOT_STORAGE_ROOT=",
        "BOARDPILOT_AUDIT_LOG_PATH=",
        "BOARDPILOT_API_KEY=",
        "BOARDPILOT_SESSION_TTL_SECONDS=",
        "BOARDPILOT_USERS_JSON=",
        "BOARDPILOT_CORS_ORIGINS=",
        "BOARDPILOT_DATABASE_URL=",
        "BOARDPILOT_REDIS_URL=",
        "NEXT_PUBLIC_API_BASE_URL=",
        "NEXT_PUBLIC_BOARDPILOT_API_KEY=",
        "NEXT_PUBLIC_BOARDPILOT_SESSION_TOKEN=",
    ):
        assert variable in env_example


def test_dockerignore_excludes_local_build_artifacts():
    api_ignore = read_repo_file("api/.dockerignore")
    web_ignore = read_repo_file("web/.dockerignore")

    for ignored in (".venv", "__pycache__", ".pytest_cache"):
        assert ignored in api_ignore

    for ignored in ("node_modules", ".next", "coverage"):
        assert ignored in web_ignore
