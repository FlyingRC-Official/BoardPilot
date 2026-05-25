FROM python:3.12-slim

WORKDIR /app
ARG PIP_INDEX_URL
ARG PIP_EXTRA_INDEX_URL
ENV PIP_DEFAULT_TIMEOUT=120 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
COPY pyproject.toml ./
RUN python -m pip install --no-cache-dir .
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host ${BOARDPILOT_API_HOST:-0.0.0.0} --port ${BOARDPILOT_API_PORT:-8000}"]
