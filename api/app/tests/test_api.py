import json
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.session import store
from app.ingestion.queue import QUEUE_NAME
from app.main import app
from app.workers.ingestion_worker import decode_ingestion_job, encode_ingestion_job


client = TestClient(app)


def setup_function():
    store.reset()


def seed_source(source_type="markdown", title="FlyingRC F4 Manual"):
    product = client.post(
        "/products",
        json={"name": "FlyingRC F4", "slug": "flyingrc-f4", "description": "Flight controller"},
    ).json()
    source = client.post(
        "/sources",
        json={
            "product_id": product["id"],
            "title": title,
            "source_type": source_type,
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


def test_ingestion_worker_message_round_trip():
    source_version_id = uuid4()
    job_id = uuid4()
    encoded = encode_ingestion_job(source_version_id, job_id)
    decoded = decode_ingestion_job(encoded)
    assert decoded.source_version_id == source_version_id
    assert decoded.job_id == job_id


def test_role_context_and_mutation_guards():
    viewer = client.get("/me", headers={"X-BoardPilot-User": "viewer-1", "X-BoardPilot-Role": "viewer"})
    assert viewer.json() == {"user_id": "viewer-1", "role": "viewer"}

    forbidden = client.post(
        "/products",
        json={"name": "Blocked", "slug": "blocked", "description": ""},
        headers={"X-BoardPilot-Role": "viewer"},
    )
    assert forbidden.status_code == 403

    allowed = client.post(
        "/products",
        json={"name": "Allowed", "slug": "allowed", "description": ""},
        headers={"X-BoardPilot-Role": "admin"},
    )
    assert allowed.status_code == 200


def test_configured_api_key_is_required_for_role_context(monkeypatch):
    monkeypatch.setattr(settings, "api_key", "test-secret")
    try:
        missing = client.get("/me", headers={"X-BoardPilot-User": "viewer-1", "X-BoardPilot-Role": "viewer"})
        assert missing.status_code == 401

        wrong = client.get(
            "/me",
            headers={"X-BoardPilot-User": "viewer-1", "X-BoardPilot-Role": "viewer", "X-BoardPilot-API-Key": "wrong"},
        )
        assert wrong.status_code == 401

        allowed = client.get(
            "/me",
            headers={"X-BoardPilot-User": "viewer-1", "X-BoardPilot-Role": "viewer", "X-BoardPilot-API-Key": "test-secret"},
        )
        assert allowed.status_code == 200
        assert allowed.json() == {"user_id": "viewer-1", "role": "viewer"}
    finally:
        monkeypatch.setattr(settings, "api_key", "")


def test_provider_config_creation_is_admin_only_and_audited():
    forbidden = client.post(
        "/provider-configs",
        json={"provider_type": "llm", "provider_name": "fake", "model_name": "fake-citation-llm"},
        headers={"X-BoardPilot-Role": "support"},
    )
    assert forbidden.status_code == 403

    created = client.post(
        "/provider-configs",
        json={"provider_type": "llm", "provider_name": "fake", "model_name": "fake-citation-llm"},
        headers={"X-BoardPilot-User": "admin-1", "X-BoardPilot-Role": "admin"},
    )
    assert created.status_code == 200
    provider_config = created.json()
    assert provider_config["enabled"] is True

    configs = client.get("/provider-configs").json()
    assert configs[0]["id"] == provider_config["id"]

    updated = client.patch(
        f"/provider-configs/{provider_config['id']}",
        json={"model_name": "fake-citation-llm-v2", "enabled": False},
        headers={"X-BoardPilot-User": "admin-2", "X-BoardPilot-Role": "admin"},
    )
    assert updated.status_code == 200
    assert updated.json()["model_name"] == "fake-citation-llm-v2"
    assert updated.json()["enabled"] is False

    providers = client.get("/providers").json()
    assert providers["configs"][0]["id"] == provider_config["id"]

    deleted = client.delete(
        f"/provider-configs/{provider_config['id']}",
        headers={"X-BoardPilot-User": "admin-3", "X-BoardPilot-Role": "admin"},
    )
    assert deleted.status_code == 200
    assert client.get("/provider-configs").json() == []

    audit_logs = client.get("/audit-logs").json()
    audit_actions = [log["action"] for log in audit_logs]
    assert "provider_config_created" in audit_actions
    assert "provider_config_updated" in audit_actions
    assert "provider_config_deleted" in audit_actions


def test_audit_logs_can_be_written_to_jsonl(tmp_path, monkeypatch):
    audit_path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(settings, "audit_log_path", str(audit_path))
    try:
        client.post(
            "/provider-configs",
            json={"provider_type": "llm", "provider_name": "fake", "model_name": "fake-citation-llm"},
            headers={"X-BoardPilot-User": "admin-jsonl", "X-BoardPilot-Role": "admin"},
        )
        records = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
        assert records[-1]["action"] == "provider_config_created"
        assert records[-1]["user_id"] == "admin-jsonl"
    finally:
        monkeypatch.setattr(settings, "audit_log_path", "")


def test_ticket_log_and_image_text_enter_source_pipeline():
    product = client.post(
        "/products",
        json={"name": "Pipeline Board", "slug": "pipeline-board", "description": ""},
    ).json()
    client.post(
        "/provider-configs",
        json={"provider_type": "ocr", "provider_name": "fake", "model_name": "fake-ocr-configured"},
    )

    ticket_payload = client.post(
        "/tickets",
        json={
            "product_id": product["id"],
            "external_id": "T-100",
            "title": "USB servo issue",
            "body": "Customer reports that USB must not power servos on Pipeline Board.",
            "tags_json": ["usb", "servo"],
            "anonymized": True,
        },
    ).json()
    assert ticket_payload["ticket"]["source_id"] == ticket_payload["source"]["id"]
    assert ticket_payload["source"]["source_type"] == "ticket_export"
    assert ticket_payload["chunks"]

    log_payload = client.post(
        "/log-sources",
        json={
            "product_id": product["id"],
            "log_type": "boot",
            "content": "BOOT_WARN USB_SERVO_POWER_BLOCKED detected during startup.",
            "device_context_json": {"firmware": "1.0"},
        },
    ).json()
    assert log_payload["log_source"]["source_id"] == log_payload["source"]["id"]
    assert "USB_SERVO_POWER_BLOCKED" in log_payload["chunks"][0]["content"]

    image_payload = client.post(
        "/image-assets",
        json={
            "product_id": product["id"],
            "storage_uri": "local://image.png",
            "image_type": "wiring_photo",
            "manual_description": "Photo shows USB connector should not feed servo rail.",
        },
    ).json()
    image_id = image_payload["image_asset"]["id"]
    assert image_payload["chunks"]

    ocr_payload = client.post(
        f"/image-assets/{image_id}/ocr",
        json={"ocr_text": "OCR label: USB CONFIG ONLY", "confidence": 0.75},
    ).json()
    assert ocr_payload["ocr_result"]["model_name"] == "fake-ocr-configured"
    assert "USB CONFIG ONLY" in ocr_payload["chunks"][0]["content"]

    ask_payload = client.post(
        "/ask",
        json={"product_id": product["id"], "question": "What does USB_SERVO_POWER_BLOCKED mean?"},
    ).json()
    evidence_text = "\n".join(item["quote"] for item in ask_payload["evidence"])
    assert "USB_SERVO_POWER_BLOCKED" in evidence_text


def test_product_source_ingestion_and_dedup():
    client.post(
        "/provider-configs",
        json={"provider_type": "embedding", "provider_name": "fake", "model_name": "fake-embedding-configured"},
    )
    client.post(
        "/provider-configs",
        json={"provider_type": "reranker", "provider_name": "fake", "model_name": "fake-reranker-configured"},
    )
    product, source, chunks = seed_source()
    assert product["name"] == "FlyingRC F4"
    assert source["source_type"] == "markdown"
    assert len(chunks) >= 1

    source_versions = client.get(f"/sources/{source['id']}/versions").json()
    version_id = source_versions[0]["id"]
    artifacts = client.get(f"/source-versions/{version_id}/artifacts").json()
    assert artifacts[0]["source_version_id"] == version_id
    assert artifacts[0]["content"]
    chunk_list = client.get(f"/source-versions/{version_id}/chunks").json()
    assert len(chunk_list) == len(chunks)
    embeddings = client.get(f"/chunks/{chunk_list[0]['id']}/embeddings").json()
    assert embeddings[0]["provider_name"] == "fake"
    assert embeddings[0]["model_name"] == "fake-embedding-configured"
    assert embeddings[0]["embedding_dimension"] == 16

    ask_payload = client.post(
        "/ask",
        json={"product_id": product["id"], "question": "Can USB power servos?"},
    ).json()
    reranked = [item for item in ask_payload["candidates"] if item["stage"] == "reranked"]
    assert reranked[0]["metadata_json"]["reranker_model_name"] == "fake-reranker-configured"

    duplicate = client.post(
        f"/sources/{source['id']}/versions/{version_id}/artifacts",
        json={"version_label": "v1-duplicate", "content": chunks[0]["content"]},
    ).json()
    assert len(duplicate["chunks"]) == 1


def test_source_disable_is_audited():
    _product, source, _chunks = seed_source()
    disabled = client.post(
        f"/sources/{source['id']}/disable",
        json={"reason": "stale pinout"},
        headers={"X-BoardPilot-User": "maintainer-1", "X-BoardPilot-Role": "support"},
    )
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "disabled"
    audit_logs = client.get("/audit-logs").json()
    audit = [log for log in audit_logs if log["action"] == "source_disabled"]
    assert audit[-1]["user_id"] == "maintainer-1"
    assert audit[-1]["after_json"]["reason"] == "stale pinout"


def test_source_version_disable_removes_chunks_from_retrieval_and_is_audited():
    product, source, chunks = seed_source()
    source_versions = client.get(f"/sources/{source['id']}/versions").json()
    version_id = source_versions[0]["id"]

    before = client.post(
        "/ask",
        json={"product_id": product["id"], "question": "Can USB power servos?"},
    ).json()
    assert before["evidence"]

    disabled = client.post(
        f"/source-versions/{version_id}/disable",
        json={"reason": "bad import"},
        headers={"X-BoardPilot-User": "maintainer-2", "X-BoardPilot-Role": "support"},
    ).json()
    assert disabled["version"]["status"] == "disabled"
    assert disabled["disabled_chunk_count"] == len(chunks)

    chunk_list = client.get(f"/source-versions/{version_id}/chunks").json()
    assert all(chunk["enabled"] is False for chunk in chunk_list)
    after = client.post(
        "/ask",
        json={"product_id": product["id"], "question": "Can USB power servos?"},
    ).json()
    assert after["evidence"] == []
    audit = [log for log in client.get("/audit-logs").json() if log["action"] == "source_version_disabled"]
    assert audit[-1]["user_id"] == "maintainer-2"
    assert audit[-1]["after_json"]["reason"] == "bad import"


def test_ingestion_job_create_list_get_and_retry():
    product, source, chunks = seed_source()
    source_versions = client.get(f"/sources/{source['id']}/versions").json()
    version_id = source_versions[0]["id"]

    created = client.post("/ingestion/jobs", json={"source_version_id": version_id}).json()
    job = created["job"]
    assert job["status"] == "completed"
    assert job["source_version_id"] == version_id
    assert job["chunk_count"] == 0

    listed = client.get("/ingestion/jobs").json()
    assert listed[0]["id"] == job["id"]

    fetched = client.get(f"/ingestion/jobs/{job['id']}").json()
    assert fetched["status"] == "completed"

    retried = client.post(f"/ingestion/jobs/{job['id']}/retry").json()
    assert retried["job"]["id"] == job["id"]
    assert retried["job"]["status"] == "completed"


def test_ingestion_job_enqueue_pushes_redis_message(monkeypatch):
    import app.ingestion.queue as ingestion_queue

    _product, source, _chunks = seed_source()
    source_versions = client.get(f"/sources/{source['id']}/versions").json()
    pushed = []

    class FakeRedis:
        def rpush(self, queue_name, message):
            pushed.append((queue_name, message))
            return 1

    monkeypatch.setattr(ingestion_queue, "get_redis_client", lambda: FakeRedis())
    response = client.post("/ingestion/jobs/enqueue", json={"source_version_id": source_versions[0]["id"]})
    assert response.status_code == 200
    payload = response.json()
    assert payload["queue"] == QUEUE_NAME
    assert payload["job"]["status"] == "queued"
    assert pushed[0][0] == QUEUE_NAME
    decoded = decode_ingestion_job(pushed[0][1])
    assert str(decoded.source_version_id) == source_versions[0]["id"]
    assert str(decoded.job_id) == payload["job"]["id"]


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


def test_csv_faq_source_upload_is_normalized_before_chunking(tmp_path, monkeypatch):
    import app.sources.service as source_service

    monkeypatch.setattr(source_service.settings, "storage_root", str(tmp_path))
    product, source, _chunks = seed_source(source_type="csv_faq", title="FlyingRC FAQ")
    response = client.post(
        f"/sources/{source['id']}/versions/upload",
        data={"version_label": "faq-upload"},
        files={
            "file": (
                "faq.csv",
                b"question,answer\nWhat is USB for?,USB is only for configuration.\n",
                "text/csv",
            )
        },
    )
    payload = response.json()
    chunk_text = payload["chunks"][0]["content"]
    assert payload["version"]["parser_version"] == "mvp-csv_faq-parser-v1"
    assert "Question: What is USB for?" in chunk_text
    assert "Answer: USB is only for configuration." in chunk_text
    assert "question,answer" not in chunk_text


def test_json_source_version_uses_source_type_parser():
    product, source, _chunks = seed_source(source_type="csv_faq", title="FlyingRC FAQ")
    response = client.post(
        f"/sources/{source['id']}/versions",
        json={
            "version_label": "faq-json",
            "content": "q,a\nCan I use USB for servos?,No. USB is for configuration only.\n",
        },
    )
    payload = response.json()
    assert payload["version"]["parser_version"] == "mvp-csv_faq-parser-v1"
    assert "Question: Can I use USB for servos?" in payload["chunks"][0]["content"]


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
    assert payload["answer"]["model_run_id"]

    model_run = client.get(f"/model-runs/{payload['answer']['model_run_id']}").json()
    assert model_run["provider_type"] == "llm"
    assert model_run["provider_name"] == "fake"
    assert model_run["status"] == "completed"
    assert model_run["token_usage_json"]["output_words"] > 0

    evidence_ids = {item["id"] for item in payload["evidence"]}
    cited_ids = {ids[0] for ids in payload["answer"]["citation_map_json"].values()}
    assert cited_ids <= evidence_ids


def test_question_attachments_link_artifacts_and_show_in_review_detail():
    product, source, _chunks = seed_source()
    version_id = client.get(f"/sources/{source['id']}/versions").json()[0]["id"]
    artifact = client.get(f"/source-versions/{version_id}/artifacts").json()[0]
    ask_payload = client.post(
        "/ask",
        json={"product_id": product["id"], "question": "Can USB power servos?"},
    ).json()

    attachment = client.post(
        f"/questions/{ask_payload['question']['id']}/attachments",
        json={"artifact_id": artifact["id"], "attachment_type": "log", "description": "customer boot log"},
    ).json()
    assert attachment["artifact_id"] == artifact["id"]
    assert attachment["attachment_type"] == "log"

    attachments = client.get(f"/questions/{ask_payload['question']['id']}/attachments").json()
    assert attachments[0]["description"] == "customer boot log"

    feedback = client.post(
        f"/answers/{ask_payload['answer']['id']}/feedback",
        json={"feedback_type": "needs_review", "notes": "inspect log attachment"},
    ).json()
    detail = client.get(f"/review-items/{feedback['id']}/detail").json()
    assert detail["attachments"][0]["id"] == attachment["id"]


def test_ask_persists_metadata_filters():
    payload = client.post(
        "/ask",
        json={"question": "Filter this query", "metadata_filters_json": {"firmware": "1.0", "page": 3}},
    ).json()
    assert payload["question"]["metadata_filters_json"] == {"firmware": "1.0", "page": 3}


def test_ask_detects_product_alias_without_hard_filtering():
    product, source, _chunks = seed_source()
    client.post(
        f"/products/{product['id']}/aliases",
        json={"alias": "F4 FC", "alias_type": "user_facing", "confidence": 0.82},
    )
    other_product = client.post(
        "/products",
        json={"name": "Other Board", "slug": "other-board", "description": "Different board"},
    ).json()
    other_source = client.post(
        "/sources",
        json={
            "product_id": other_product["id"],
            "title": "Other Board Manual",
            "source_type": "markdown",
            "trust_level": "official",
        },
    ).json()
    client.post(
        f"/sources/{other_source['id']}/versions",
        json={"version_label": "v1", "content": "USB power on this board has unrelated constraints."},
    )

    payload = client.post("/ask", json={"question": "For the F4 FC, can USB power servos?"}).json()
    detected = payload["question"]["detected_entities_json"]["products"][0]
    assert detected["product_id"] == product["id"]
    assert detected["alias"] == "F4 FC"
    assert "flyingrc f4" in payload["question"]["normalized_text"]

    filters = payload["retrieval_run"]["filter_plan_json"]["filters"]
    assert filters[0]["type"] == "soft_boost"
    assert filters[0]["value"] == product["id"]
    assert not any(item["type"] == "hard_filter" for item in filters)
    top_reranked = [candidate for candidate in payload["candidates"] if candidate["stage"] == "reranked"][0]
    assert top_reranked["metadata_json"]["soft_boost_score"] > 0


def test_explicit_product_selection_still_uses_hard_filter():
    product, _source, _chunks = seed_source()
    client.post(
        f"/products/{product['id']}/aliases",
        json={"alias": "F4 FC", "alias_type": "user_facing", "confidence": 0.82},
    )
    payload = client.post(
        "/ask",
        json={"product_id": product["id"], "question": "For the F4 FC, can USB power servos?"},
    ).json()
    filters = payload["retrieval_run"]["filter_plan_json"]["filters"]
    assert filters == [{"type": "hard_filter", "field": "product_id", "value": product["id"]}]


def test_insufficient_evidence_routes_to_review():
    response = client.post("/ask", json={"question": "What is the secret factory calibration code?"})
    payload = response.json()
    assert payload["answer"]["evidence_sufficiency"] == "insufficient"
    assert payload["review_item"]["status"] == "open"


def test_answer_feedback_creates_review_item():
    product, _source, _chunks = seed_source()
    ask_payload = client.post(
        "/ask",
        json={"product_id": product["id"], "question": "Can I power servos from USB?"},
    ).json()
    feedback = client.post(
        f"/answers/{ask_payload['answer']['id']}/feedback",
        json={"feedback_type": "missing_source", "notes": "Need a stronger source citation."},
    )
    assert feedback.status_code == 200
    assert feedback.json()["source_type"] == "missing_source"
    assert feedback.json()["answer_id"] == ask_payload["answer"]["id"]
    assert feedback.json()["reviewer_notes"] == "Need a stronger source citation."


def test_llm_provider_config_sets_model_run_identity_and_cost():
    product, _source, _chunks = seed_source()
    client.post(
        "/provider-configs",
        json={
            "provider_type": "llm",
            "provider_name": "fake",
            "model_name": "fake-citation-llm-costed",
            "config_json": {"input_cost_per_1k_words": 0.25, "output_cost_per_1k_words": 0.5, "currency": "USD"},
        },
    )

    payload = client.post(
        "/ask",
        json={"product_id": product["id"], "question": "Can I power servos from USB?"},
    ).json()
    assert payload["answer"]["model_name"] == "fake-citation-llm-costed"
    model_run = client.get(f"/model-runs/{payload['answer']['model_run_id']}").json()
    assert model_run["model_name"] == "fake-citation-llm-costed"
    assert model_run["cost_json"]["total_cost"] > 0


def test_eval_run_records_metrics_and_can_route_failure_to_review():
    product, _source, chunks = seed_source()
    client.post(
        "/provider-configs",
        json={
            "provider_type": "llm",
            "provider_name": "fake",
            "model_name": "fake-citation-llm-costed",
            "config_json": {"input_cost_per_1k_words": 0.25, "output_cost_per_1k_words": 0.5},
        },
    )
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
    assert "evidence_sufficiency_rate" in eval_run["summary_metrics_json"]
    assert "failure_category_distribution" in eval_run["summary_metrics_json"]
    assert "latency_p50_ms" in eval_run["summary_metrics_json"]
    assert "latency_p95_ms" in eval_run["summary_metrics_json"]
    assert eval_run["provider_config_json"]["llm"]["model_name"] == "fake-citation-llm-costed"
    assert eval_run["summary_metrics_json"]["model_cost"] > 0
    assert results[0]["eval_case_id"] == case["id"]

    review = client.post(f"/eval-results/{results[0]['id']}/to-review").json()
    assert review["source_type"] == "eval_failure"


def test_eval_case_expected_evidence_fields_can_be_listed_and_updated():
    product, _source, chunks = seed_source()
    case = client.post(
        "/eval-cases",
        json={
            "product_id": product["id"],
            "question_text": "Which chunk proves USB power policy?",
            "expected_chunk_ids_json": [chunks[0]["id"]],
            "expected_answer_points_json": ["USB connector policy"],
            "tags_json": ["usb"],
        },
    ).json()
    listed = client.get("/eval-cases").json()
    assert listed[0]["expected_chunk_ids_json"] == [chunks[0]["id"]]

    updated = client.patch(
        f"/eval-cases/{case['id']}",
        json={"expected_chunk_ids_json": [chunks[-1]["id"]], "difficulty": "hard", "active": False},
    ).json()
    assert updated["expected_chunk_ids_json"] == [chunks[-1]["id"]]
    assert updated["difficulty"] == "hard"
    assert updated["active"] is False


def test_seed_eval_cases_run_batch_with_at_least_20_cases():
    seed_payload = client.post("/eval-cases/seed").json()
    assert seed_payload["case_count"] >= 20

    run_payload = client.post("/eval-runs", json={"name": "seed corpus"}).json()
    assert run_payload["eval_run"]["summary_metrics_json"]["case_count"] >= 20
    assert len(run_payload["results"]) >= 20

    second_run = client.post("/eval-runs", json={"name": "seed corpus second"}).json()
    comparison = client.get(
        "/eval-runs/compare",
        params={"run_a": run_payload["eval_run"]["id"], "run_b": second_run["eval_run"]["id"]},
    ).json()
    assert comparison["baseline"]["id"] == run_payload["eval_run"]["id"]
    assert comparison["candidate"]["id"] == second_run["eval_run"]["id"]
    assert "recall_at_20" in comparison["deltas"]


def test_review_to_faq_reingests_approved_answer_as_source_material():
    product, _source, _chunks = seed_source()
    ask_payload = client.post(
        "/ask",
        json={"product_id": product["id"], "question": "What is the secret factory calibration code?"},
    ).json()
    review_item = ask_payload["review_item"]
    assert review_item
    client.patch(
        f"/review-items/{review_item['id']}",
        json={"edited_answer_text": "Use the documented calibration flow only. Do not use secret factory codes."},
    )

    faq_payload = client.post(f"/review-items/{review_item['id']}/to-faq").json()
    assert faq_payload["status"] == "converted_to_faq"
    assert faq_payload["approved_faq"]["question_text"].startswith("What is the secret")
    assert faq_payload["approved_faq"]["answer_text"].startswith("Use the documented calibration")
    assert faq_payload["source"]["source_type"] == "approved_faq"
    assert faq_payload["chunks"]

    rerun = client.post(
        "/ask",
        json={"product_id": product["id"], "question": "secret factory calibration code"},
    ).json()
    evidence_text = "\n".join(item["quote"] for item in rerun["evidence"])
    assert "secret factory calibration code" in evidence_text


def test_review_to_eval_case_preserves_expected_evidence_and_answer_points():
    product, _source, _chunks = seed_source()
    ask_payload = client.post(
        "/ask",
        json={"product_id": product["id"], "question": "Can I power servos from USB?"},
    ).json()
    review_item = client.post(
        f"/answers/{ask_payload['answer']['id']}/feedback",
        json={"feedback_type": "user_feedback", "notes": "Make this a regression."},
    ).json()
    client.patch(
        f"/review-items/{review_item['id']}",
        json={"edited_answer_text": "USB is for configuration only. Do not power servos from USB."},
    )

    eval_case = client.post(f"/review-items/{review_item['id']}/to-eval-case").json()
    assert eval_case["question_text"] == "Can I power servos from USB?"
    assert eval_case["expected_chunk_ids_json"]
    assert eval_case["expected_source_ids_json"]
    assert eval_case["expected_answer_points_json"][0].startswith("USB is for configuration")
    assert "review_regression" in eval_case["tags_json"]


def test_review_item_detail_links_question_answer_evidence_and_trace():
    product, _source, _chunks = seed_source()
    ask_payload = client.post(
        "/ask",
        json={"product_id": product["id"], "question": "Can I power servos from USB?"},
    ).json()
    review_item = client.post(
        f"/answers/{ask_payload['answer']['id']}/feedback",
        json={"feedback_type": "user_feedback", "notes": "Inspect retrieval trace."},
    ).json()

    detail = client.get(f"/review-items/{review_item['id']}/detail").json()
    assert detail["item"]["id"] == review_item["id"]
    assert detail["question"]["raw_text"] == "Can I power servos from USB?"
    assert detail["answer"]["id"] == ask_payload["answer"]["id"]
    assert detail["evidence"]
    assert detail["candidates"]


def test_review_item_detail_includes_eval_failure_context():
    product, _source, chunks = seed_source()
    case = client.post(
        "/eval-cases",
        json={
            "product_id": product["id"],
            "question_text": "How should I treat USB power?",
            "expected_chunk_ids_json": [chunks[-1]["id"]],
        },
    ).json()
    run_payload = client.post("/eval-runs", json={"name": "review detail eval"}).json()
    result = run_payload["results"][0]
    review = client.post(f"/eval-results/{result['id']}/to-review").json()

    detail = client.get(f"/review-items/{review['id']}/detail").json()
    assert detail["eval_result"]["eval_case_id"] == case["id"]
    assert "recall_at_20" in detail["eval_result"]
    assert detail["question"]["raw_text"] == "How should I treat USB power?"


def test_review_approval_requires_failure_category():
    ask_payload = client.post("/ask", json={"question": "What is undocumented?"}).json()
    review_item = ask_payload["review_item"]

    missing_category = client.post(f"/review-items/{review_item['id']}/approve", json={})
    assert missing_category.status_code == 422
    assert "failure_category" in missing_category.json()["detail"]

    patched = client.patch(
        f"/review-items/{review_item['id']}",
        json={"failure_category": "bad_rerank", "reviewer_notes": "Reranker missed the useful quote."},
        headers={"X-BoardPilot-User": "reviewer-1", "X-BoardPilot-Role": "reviewer"},
    )
    assert patched.status_code == 200
    assert patched.json()["failure_category"] == "bad_rerank"
    assert patched.json()["reviewer_notes"].startswith("Reranker missed")

    approved = client.post(
        f"/review-items/{review_item['id']}/approve",
        json={"failure_category": "insufficient_evidence"},
        headers={"X-BoardPilot-User": "reviewer-1", "X-BoardPilot-Role": "reviewer"},
    )
    assert approved.status_code == 200
    assert approved.json()["failure_category"] == "insufficient_evidence"
    audit_actions = [item["action"] for item in client.get("/audit-logs").json()]
    assert "review_item_updated" in audit_actions

    audit_logs = client.get("/audit-logs").json()
    review_audit = [log for log in audit_logs if log["action"] == "review_approved"]
    assert review_audit
    assert review_audit[-1]["user_id"] == "reviewer-1"
    assert review_audit[-1]["entity_id"] == review_item["id"]


def test_review_can_be_marked_as_needing_source_update():
    ask_payload = client.post("/ask", json={"question": "What source needs updating?"}).json()
    review_item = ask_payload["review_item"]
    marked = client.post(
        f"/review-items/{review_item['id']}/source-update-needed",
        json={"failure_category": "stale_source"},
        headers={"X-BoardPilot-User": "reviewer-2", "X-BoardPilot-Role": "reviewer"},
    )
    assert marked.status_code == 200
    assert marked.json()["status"] == "needs_source_update"
    assert marked.json()["failure_category"] == "stale_source"
    audit_actions = [item["action"] for item in client.get("/audit-logs").json()]
    assert "review_marked_source_update_needed" in audit_actions


def test_source_and_eval_case_changes_are_audit_logged():
    product, source, _chunks = seed_source()
    client.patch(
        f"/sources/{source['id']}",
        json={"status": "disabled"},
        headers={"X-BoardPilot-User": "maintainer-1", "X-BoardPilot-Role": "support"},
    )
    case = client.post(
        "/eval-cases",
        json={"product_id": product["id"], "question_text": "Initial eval question"},
    ).json()
    client.patch(
        f"/eval-cases/{case['id']}",
        json={"difficulty": "hard"},
        headers={"X-BoardPilot-User": "eval-1", "X-BoardPilot-Role": "reviewer"},
    )

    audit_logs = client.get("/audit-logs").json()
    source_audit = [log for log in audit_logs if log["action"] == "source_updated"]
    eval_audit = [log for log in audit_logs if log["action"] == "eval_case_modified"]
    assert source_audit[-1]["before_json"]["status"] == "active"
    assert source_audit[-1]["after_json"]["status"] == "disabled"
    assert source_audit[-1]["user_id"] == "maintainer-1"
    assert eval_audit[-1]["before_json"]["difficulty"] == "normal"
    assert eval_audit[-1]["after_json"]["difficulty"] == "hard"
