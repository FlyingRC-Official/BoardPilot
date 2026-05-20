from fastapi.testclient import TestClient

from app.db.session import store
from app.main import app


client = TestClient(app)


def setup_function():
    store.reset()


def seed_source():
    product = client.post(
        "/products",
        json={"name": "FlyingRC F4", "slug": "flyingrc-f4", "description": "Flight controller"},
    ).json()
    source = client.post(
        "/sources",
        json={
            "product_id": product["id"],
            "title": "FlyingRC F4 Manual",
            "source_type": "markdown",
            "trust_level": "official",
        },
    ).json()
    version_payload = {
        "version_label": "v1",
        "content": (
            "The FlyingRC F4 supports PWM outputs on M1 to M4.\n\n"
            "For DShot setup, enable bdshot only after confirming timer mapping and ESC firmware support.\n\n"
            "USB power is for configuration. Do not power servos from the USB connector."
        ),
    }
    version_response = client.post(f"/sources/{source['id']}/versions", json=version_payload).json()
    chunks = version_response["chunks"]
    return product, source, chunks


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_product_source_ingestion_and_dedup():
    product, source, chunks = seed_source()
    assert product["name"] == "FlyingRC F4"
    assert source["source_type"] == "markdown"
    assert len(chunks) >= 1

    source_versions = client.get(f"/sources/{source['id']}/versions").json()
    version_id = source_versions[0]["id"]
    chunk_list = client.get(f"/source-versions/{version_id}/chunks").json()
    assert len(chunk_list) == len(chunks)

    duplicate = client.post(
        f"/sources/{source['id']}/versions/{version_id}/artifacts",
        json={"version_label": "v1-duplicate", "content": chunks[0]["content"]},
    ).json()
    assert len(duplicate["chunks"]) == 1


def test_upload_source_version_stores_artifact_and_creates_chunks(tmp_path, monkeypatch):
    import app.sources.service as source_service

    monkeypatch.setattr(source_service.settings, "storage_root", str(tmp_path))
    product, source, _chunks = seed_source()
    response = client.post(
        f"/sources/{source['id']}/versions/upload",
        data={"version_label": "upload-v1"},
        files={"file": ("manual.md", b"Uploaded manual says USB is configuration only.", "text/markdown")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["version"]["version_label"] == "upload-v1"
    assert payload["artifact"]["metadata_json"]["original_filename"] == "manual.md"
    assert payload["artifact"]["size_bytes"] > 0
    assert payload["chunks"][0]["content"].startswith("Uploaded manual")


def test_ask_creates_retrieval_evidence_answer_and_citations():
    product, _source, chunks = seed_source()
    response = client.post(
        "/ask",
        json={"product_id": product["id"], "question": "Can I power servos from the USB connector?"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["question"]["raw_text"].startswith("Can I")
    assert payload["retrieval_run"]["status"] == "completed"
    assert payload["evidence"]
    assert payload["answer"]["citation_map_json"]

    evidence_ids = {item["id"] for item in payload["evidence"]}
    cited_ids = {ids[0] for ids in payload["answer"]["citation_map_json"].values()}
    assert cited_ids <= evidence_ids


def test_insufficient_evidence_routes_to_review():
    response = client.post("/ask", json={"question": "What is the secret factory calibration code?"})
    payload = response.json()
    assert payload["answer"]["evidence_sufficiency"] == "insufficient"
    assert payload["review_item"]["status"] == "open"


def test_eval_run_records_metrics_and_can_route_failure_to_review():
    product, _source, chunks = seed_source()
    case = client.post(
        "/eval-cases",
        json={
            "product_id": product["id"],
            "question_text": "How should I treat USB power?",
            "expected_chunk_ids_json": [chunks[-1]["id"]],
            "expected_answer_points_json": ["USB is for configuration"],
        },
    ).json()
    assert case["active"] is True

    run_payload = client.post("/eval-runs", json={"name": "seed smoke"}).json()
    eval_run = run_payload["eval_run"]
    results = run_payload["results"]
    assert eval_run["summary_metrics_json"]["case_count"] == 1
    assert "recall_at_20" in eval_run["summary_metrics_json"]
    assert results[0]["eval_case_id"] == case["id"]

    review = client.post(f"/eval-results/{results[0]['id']}/to-review").json()
    assert review["source_type"] == "eval_failure"
