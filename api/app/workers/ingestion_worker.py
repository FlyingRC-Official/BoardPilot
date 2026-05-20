from __future__ import annotations

import argparse
import json
import logging
import time
from dataclasses import dataclass
from uuid import UUID

from app.core.config import settings
from app.ingestion.jobs import run_ingestion_job

QUEUE_NAME = "boardpilot:ingestion_jobs"

logger = logging.getLogger("boardpilot.ingestion_worker")


@dataclass
class IngestionJobMessage:
    source_version_id: UUID


def encode_ingestion_job(source_version_id: UUID) -> str:
    return json.dumps({"source_version_id": str(source_version_id)}, sort_keys=True)


def decode_ingestion_job(raw_message: bytes | str) -> IngestionJobMessage:
    payload = json.loads(raw_message.decode("utf-8") if isinstance(raw_message, bytes) else raw_message)
    return IngestionJobMessage(source_version_id=UUID(str(payload["source_version_id"])))


def process_message(raw_message: bytes | str) -> None:
    message = decode_ingestion_job(raw_message)
    run_ingestion_job(message.source_version_id)


def run_worker(once: bool = False, poll_timeout_seconds: int = 5) -> None:
    from redis import Redis

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    redis_client = Redis.from_url(settings.redis_url)
    logger.info("listening queue=%s redis=%s", QUEUE_NAME, settings.redis_url)
    while True:
        item = redis_client.blpop(QUEUE_NAME, timeout=poll_timeout_seconds)
        if item:
            _queue_name, raw_message = item
            process_message(raw_message)
        if once:
            return
        time.sleep(0.1)


def main() -> None:
    parser = argparse.ArgumentParser(description="BoardPilot ingestion worker")
    parser.add_argument("--once", action="store_true", help="Poll once and exit")
    parser.add_argument("--poll-timeout-seconds", type=int, default=5)
    args = parser.parse_args()
    run_worker(once=args.once, poll_timeout_seconds=args.poll_timeout_seconds)


if __name__ == "__main__":
    main()
