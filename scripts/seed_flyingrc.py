#!/usr/bin/env python3
"""Seed a BoardPilot deployment with FlyingRC starter products, sources, and eval cases."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "flyingrc_initial_knowledge.json"


class BoardPilotClient:
    def __init__(self, api_base: str, api_key: str = "") -> None:
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if self.api_key:
            headers["X-BoardPilot-API-Key"] = self.api_key
        request = urllib.request.Request(f"{self.api_base}{path}", data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{method} {path} failed with HTTP {exc.code}: {detail}") from exc
        return json.loads(raw.decode("utf-8")) if raw else None

    def get(self, path: str) -> Any:
        return self.request("GET", path)

    def post(self, path: str, payload: dict[str, Any]) -> Any:
        return self.request("POST", path, payload)


def find_by(items: list[dict[str, Any]], **conditions: str) -> dict[str, Any] | None:
    for item in items:
        if all(item.get(key) == value for key, value in conditions.items()):
            return item
    return None


def first_chunk_id(chunks: list[dict[str, Any]], source_title: str) -> str | None:
    source_title_lower = source_title.lower()
    for chunk in chunks:
        title_path = str(chunk.get("title_path", "")).lower()
        content = str(chunk.get("content", "")).lower()
        if source_title_lower in title_path or any(word in content for word in source_title_lower.split()[:3]):
            return chunk["id"]
    return chunks[0]["id"] if chunks else None


def seed(client: BoardPilotClient, dataset: dict[str, Any]) -> dict[str, int]:
    counts = {"products": 0, "aliases": 0, "sources": 0, "versions": 0, "eval_cases": 0}
    products = client.get("/products")
    eval_cases = client.get("/eval-cases")

    for product_spec in dataset["products"]:
        product = find_by(products, slug=product_spec["slug"])
        if product is None:
            product = client.post(
                "/products",
                {
                    "name": product_spec["name"],
                    "slug": product_spec["slug"],
                    "description": product_spec["description"],
                },
            )
            products.append(product)
            counts["products"] += 1

        aliases = client.get(f"/products/{product['id']}/aliases")
        for alias in product_spec.get("aliases", []):
            if find_by(aliases, alias=alias) is None:
                aliases.append(
                    client.post(
                        f"/products/{product['id']}/aliases",
                        {"alias": alias, "alias_type": "user_facing", "confidence": 0.9},
                    )
                )
                counts["aliases"] += 1

        sources = client.get("/sources")
        source_chunks_by_title: dict[str, list[dict[str, Any]]] = {}
        source_ids_by_title: dict[str, str] = {}
        for source_spec in product_spec.get("sources", []):
            source = next(
                (
                    item
                    for item in sources
                    if item.get("product_id") == product["id"] and item.get("title") == source_spec["title"]
                ),
                None,
            )
            if source is None:
                source = client.post(
                    "/sources",
                    {
                        "product_id": product["id"],
                        "title": source_spec["title"],
                        "source_type": source_spec["source_type"],
                        "trust_level": source_spec["trust_level"],
                    },
                )
                sources.append(source)
                counts["sources"] += 1

            source_ids_by_title[source_spec["title"]] = source["id"]
            versions = client.get(f"/sources/{source['id']}/versions")
            matching_version = find_by(versions, version_label=source_spec["version_label"])
            if matching_version is None:
                bundle = client.post(
                    f"/sources/{source['id']}/versions",
                    {"version_label": source_spec["version_label"], "content": source_spec["content"]},
                )
                chunks = bundle.get("chunks", [])
                counts["versions"] += 1
            elif matching_version.get("status") == "created":
                chunks = client.get(f"/source-versions/{matching_version['id']}/chunks")
            else:
                chunks = []
            source_chunks_by_title[source_spec["title"]] = chunks

        for case_spec in product_spec.get("eval_cases", []):
            if find_by(eval_cases, question_text=case_spec["question_text"]) is not None:
                continue
            source_title = case_spec.get("expected_source_title", "")
            chunks = source_chunks_by_title.get(source_title, [])
            expected_chunk_id = first_chunk_id(chunks, source_title)
            expected_source_id = source_ids_by_title.get(source_title)
            payload = {
                "product_id": product["id"],
                "question_text": case_spec["question_text"],
                "expected_source_ids_json": [expected_source_id] if expected_source_id else [],
                "expected_chunk_ids_json": [expected_chunk_id] if expected_chunk_id else [],
                "expected_answer_points_json": case_spec.get("expected_answer_points_json", []),
                "tags_json": case_spec.get("tags_json", []),
                "difficulty": case_spec.get("difficulty", "normal"),
                "active": True,
            }
            eval_cases.append(client.post("/eval-cases", payload))
            counts["eval_cases"] += 1

    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default="http://127.0.0.1:8000", help="BoardPilot API base URL")
    parser.add_argument("--api-key", default="", help="BoardPilot API key for private deployments")
    parser.add_argument("--data", default=str(DEFAULT_DATA_PATH), help="FlyingRC seed dataset JSON path")
    args = parser.parse_args()

    dataset = json.loads(Path(args.data).read_text(encoding="utf-8"))
    client = BoardPilotClient(args.api_base, args.api_key)
    client.get("/health")
    counts = seed(client, dataset)
    print(json.dumps({"status": "ok", "created": counts}, ensure_ascii=False, indent=2))
    print("Acceptance questions:")
    for question in dataset.get("acceptance_questions", []):
        print(f"- {question}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
