FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir .
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host ${BOARDPILOT_API_HOST:-0.0.0.0} --port ${BOARDPILOT_API_PORT:-8000}"]
