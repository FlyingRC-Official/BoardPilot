import json
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import Settings, settings
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


def test_version_and_provider_metadata_endpoints():
    version = client.get("/version")
    assert version.status_code == 200
    assert version.json()["version"] == "0.1.0"
    assert version.json()["environment"] == settings.environment

    providers = client.get("/providers")
    assert providers.status_code == 200
    assert providers.json()["llm"] == settings.llm_provider
    assert providers.json()["embedding"] == settings.embedding_provider
    assert providers.json()["reranker"] == settings.reranker_provider
    assert providers.json()["ocr"] == settings.ocr_provider
    assert providers.json()["configs"] == []


def test_env_example_documents_known_backend_settings():
    project_root = Path(__file__).resolve().parents[3]
    env_text = (project_root / ".env.example").read_text(encoding="utf-8")
    env_vars = {
        line.split("=", 1)[0]
        for line in env_text.splitlines()
        if line and not line.startswith("#") and "=" in line
    }
    backend_vars = {name for name in env_vars if name.startswith("BOARDPILOT_")}
    known_backend_vars = {f"BOARDPILOT_{name.upper()}" for name in Settings.model_fields}
    known_backend_vars.add("BOARDPILOT_ENV")

    assert backend_vars <= known_backend_vars
    assert "BOARDPILOT_API_KEY" in env_vars
    assert "NEXT_PUBLIC_BOARDPILOT_API_KEY" in env_vars
    assert "Required for private deployments" in env_text
    dockerfile = (project_root / "api" / "Dockerfile").read_text(encoding="utf-8")
    assert "${BOARDPILOT_API_HOST:-0.0.0.0}" in dockerfile
    assert "${BOARDPILOT_API_PORT:-8000}" in dockerfile


def test_local_web_origin_cors_preflight():
    response = client.options(
        "/products",
        headers={
            "Origin": "http://127.0.0.1:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-BoardPilot-API-Key",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"
    assert "X-BoardPilot-API-Key" in response.headers["access-control-allow-headers"]


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
    maintainer = client.get("/me", headers={"X-BoardPilot-User": "maintainer-1", "X-BoardPilot-Role": "maintainer"})
    assert maintainer.json() == {"user_id": "maintainer-1", "role": "maintainer"}
    evaluator = client.get("/me", headers={"X-BoardPilot-User": "evaluator-1", "X-BoardPilot-Role": "evaluator"})
    assert evaluator.json() == {"user_id": "evaluator-1", "role": "evaluator"}

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

    maintainer_source = client.post(
        "/sources",
        json={
            "product_id": allowed.json()["id"],
            "title": "Maintainer Manual",
            "source_type": "markdown",
            "trust_level": "official",
        },
        headers={"X-BoardPilot-User": "maintainer-1", "X-BoardPilot-Role": "maintainer"},
    )
    assert maintainer_source.status_code == 200

    maintainer_alias = client.post(
        f"/products/{allowed.json()['id']}/aliases",
        json={"alias": "Allowed Board", "alias_type": "user_facing", "confidence": 0.9},
        headers={"X-BoardPilot-User": "maintainer-1", "X-BoardPilot-Role": "maintainer"},
    )
    assert maintainer_alias.status_code == 200

    evaluator_case = client.post(
        "/eval-cases",
        json={"question_text": "Does the evaluator role work?", "product_id": allowed.json()["id"]},
        headers={"X-BoardPilot-User": "evaluator-1", "X-BoardPilot-Role": "evaluator"},
    )
    assert evaluator_case.status_code == 200
    evaluator_run = client.post(
        "/eval-runs",
        json={"name": "evaluator role smoke"},
        headers={"X-BoardPilot-User": "evaluator-1", "X-BoardPilot-Role": "evaluator"},
    )
    assert evaluator_run.status_code == 200

    evaluator_provider = client.post(
        "/provider-configs",
        json={"provider_type": "llm", "provider_name": "fake", "model_name": "fake-citation-llm"},
        headers={"X-BoardPilot-User": "evaluator-1", "X-BoardPilot-Role": "evaluator"},
    )
    assert evaluator_provider.status_code == 403


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


def test_configured_api_key_protects_read_endpoints_but_allows_health_and_preflight(monkeypatch):
    monkeypatch.setattr(settings, "api_key", "read-secret")
    try:
        health = client.get("/health")
        assert health.status_code == 200

        preflight = client.options(
            "/products",
            headers={
                "Origin": "http://127.0.0.1:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-BoardPilot-API-Key",
            },
        )
        assert preflight.status_code == 200

        missing = client.get("/products")
        assert missing.status_code == 401

        wrong = client.get("/products", headers={"X-BoardPilot-API-Key": "wrong"})
        assert wrong.status_code == 401

        allowed = client.get("/products", headers={"X-BoardPilot-API-Key": "read-secret"})
        assert allowed.status_code == 200
    finally:
        monkeypatch.setattr(settings, "api_key", "")


def test_ask_uses_role_context_api_key_and_question_user(monkeypatch):
    product, _source, _chunks = seed_source()

    forbidden = client.post(
        "/ask",
        json={"product_id": product["id"], "question": "Can USB power servos?"},
        headers={"X-BoardPilot-User": "viewer-ask", "X-BoardPilot-Role": "viewer"},
    )
    assert forbidden.status_code == 403

    allowed = client.post(
        "/ask",
        json={"product_id": product["id"], "question": "Can USB power servos?"},
        headers={"X-BoardPilot-User": "support-ask", "X-BoardPilot-Role": "support"},
    )
    assert allowed.status_code == 200
    assert allowed.json()["question"]["user_id"] == "support-ask"

    monkeypatch.setattr(settings, "api_key", "ask-secret")
    try:
        missing_key = client.post(
            "/ask",
            json={"product_id": product["id"], "question": "Can USB power servos?"},
            headers={"X-BoardPilot-User": "support-ask", "X-BoardPilot-Role": "support"},
        )
        assert missing_key.status_code == 401

        with_key = client.post(
            "/ask",
            json={"product_id": product["id"], "question": "Can USB power servos?"},
            headers={
                "X-BoardPilot-User": "support-keyed",
                "X-BoardPilot-Role": "support",
                "X-BoardPilot-API-Key": "ask-secret",
            },
        )
        assert with_key.status_code == 200
        assert with_key.json()["question"]["user_id"] == "support-keyed"
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


def test_enabled_provider_configs_are_exclusive_per_provider_type():
    first = client.post(
        "/provider-configs",
        json={"provider_type": "llm", "provider_name": "fake", "model_name": "fake-citation-llm"},
        headers={"X-BoardPilot-User": "admin-provider-1", "X-BoardPilot-Role": "admin"},
    ).json()
    second = client.post(
        "/provider-configs",
        json={"provider_type": "llm", "provider_name": "openai", "model_name": "gpt-example"},
        headers={"X-BoardPilot-User": "admin-provider-2", "X-BoardPilot-Role": "admin"},
    ).json()

    configs = {config["id"]: config for config in client.get("/provider-configs").json()}
    assert configs[first["id"]]["enabled"] is False
    assert configs[second["id"]]["enabled"] is True

    client.patch(
        f"/provider-configs/{first['id']}",
        json={"enabled": True},
        headers={"X-BoardPilot-User": "admin-provider-3", "X-BoardPilot-Role": "admin"},
    )

    configs = {config["id"]: config for config in client.get("/provider-configs").json()}
    assert configs[first["id"]]["enabled"] is True
    assert configs[second["id"]]["enabled"] is False


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
    ocr_results = client.get(f"/image-assets/{image_id}/ocr-results").json()
    assert ocr_results[0]["id"] == ocr_payload["ocr_result"]["id"]
    assert ocr_results[0]["status"] == "completed"
    assert ocr_results[0]["ocr_text"] == "OCR label: USB CONFIG ONLY"

    ask_payload = client.post(
        "/ask",
        json={"product_id": product["id"], "question": "What does USB_SERVO_POWER_BLOCKED mean?"},
    ).json()
    evidence_text = "\n".join(item["quote"] for item in ask_payload["evidence"])
    assert "USB_SERVO_POWER_BLOCKED" in evidence_text


def test_uploaded_image_asset_is_stored_and_manual_description_is_ingested(tmp_path, monkeypatch):
    import app.main as main_module

    monkeypatch.setattr(main_module.settings, "storage_root", str(tmp_path))
    product = client.post(
        "/products",
        json={"name": "FlyingRC F4", "slug": "flyingrc-f4", "description": "Flight controller"},
    ).json()
    response = client.post(
        "/image-assets/upload",
        data={
            "product_id": product["id"],
            "image_type": "wiring_photo",
            "manual_description": "IMAGE_UPLOAD_USB_ONLY: USB is for configuration, not servo power.",
        },
        files={"file": ("wiring photo.png", b"\x89PNG\r\nfake-image", "image/png")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["upload"]["filename"] == "wiring photo.png"
    assert payload["upload"]["mime_type"] == "image/png"
    assert payload["upload"]["size_bytes"] > 0
    assert payload["image_asset"]["storage_uri"].endswith("-wiring_photo.png")
    assert payload["source"]["source_type"] == "image"
    assert "IMAGE_UPLOAD_USB_ONLY" in payload["chunks"][0]["content"]
    assert (tmp_path / payload["image_asset"]["storage_uri"].replace(str(tmp_path) + "/", "")).exists()

    ask_payload = client.post(
        "/ask",
        json={"product_id": product["id"], "question": "What does IMAGE_UPLOAD_USB_ONLY say?"},
    ).json()
    assert any("IMAGE_UPLOAD_USB_ONLY" in item["quote"] for item in ask_payload["evidence"])


def test_configured_ocr_provider_text_is_ingested_without_manual_payload(monkeypatch):
    import app.main as main_module
    from app.providers.base import OCRResult

    product = client.post(
        "/products",
        json={"name": "OCR Provider Board", "slug": "ocr-provider-board", "description": ""},
    ).json()
    client.post(
        "/provider-configs",
        json={
            "provider_type": "ocr",
            "provider_name": "tesseract",
            "model_name": "tesseract-eng",
            "config_json": {"language": "eng"},
        },
    )
    image_payload = client.post(
        "/image-assets",
        json={
            "product_id": product["id"],
            "storage_uri": "local://ocr-provider-board.png",
            "image_type": "label",
        },
    ).json()

    def fake_ocr(_provider_config, _image_uri):
        return OCRResult("tesseract", "tesseract-eng", 12, text="OCR_PROVIDER_J3_CAN_FD", confidence=0.91)

    monkeypatch.setattr(main_module, "run_configured_ocr", fake_ocr)
    ocr_payload = client.post(f"/image-assets/{image_payload['image_asset']['id']}/ocr", json={}).json()

    assert ocr_payload["ocr_result"]["provider_name"] == "tesseract"
    assert ocr_payload["ocr_result"]["ocr_text"] == "OCR_PROVIDER_J3_CAN_FD"
    assert ocr_payload["ocr_result"]["confidence"] == 0.91
    assert ocr_payload["version"]["status"] == "ingested"
    assert "OCR_PROVIDER_J3_CAN_FD" in ocr_payload["chunks"][0]["content"]


def test_tesseract_ocr_provider_reports_missing_executable(monkeypatch):
    import app.providers.ocr as ocr_module
    from app.models.schemas import ProviderConfig

    monkeypatch.setattr(ocr_module, "which", lambda _name: None)
    result = ocr_module.run_configured_ocr(
        ProviderConfig(
            provider_type="ocr",
            provider_name="tesseract",
            model_name="tesseract-custom",
            config_json={"language": "eng"},
        ),
        "/tmp/nonexistent.png",
    )

    assert result.provider_name == "tesseract"
    assert result.model_name == "tesseract-custom"
    assert result.text == ""
    assert "tesseract executable is not installed" in result.error_message


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
    assert duplicate["version"]["id"] == version_id
    assert len(duplicate["chunks"]) == 1
    assert len(client.get(f"/sources/{source['id']}/versions").json()) == 1
    version_artifacts = client.get(f"/source-versions/{version_id}/artifacts").json()
    assert len(version_artifacts) == 2
    assert all(artifact["source_version_id"] == version_id for artifact in version_artifacts)


def test_child_list_endpoints_distinguish_missing_parent_from_empty_children():
    missing_id = str(uuid4())
    assert client.get(f"/products/{missing_id}/aliases").status_code == 404
    assert client.get(f"/sources/{missing_id}/versions").status_code == 404
    assert client.get(f"/source-versions/{missing_id}/chunks").status_code == 404
    assert client.get(f"/source-versions/{missing_id}/artifacts").status_code == 404
    assert client.get(f"/questions/{missing_id}/attachments").status_code == 404
    assert client.get(f"/retrieval-runs/{missing_id}/candidates").status_code == 404
    assert client.get(f"/eval-runs/{missing_id}/results").status_code == 404

    product = client.post(
        "/products",
        json={"name": "Empty Child Board", "slug": "empty-child-board", "description": ""},
    ).json()
    source = client.post(
        "/sources",
        json={
            "product_id": product["id"],
            "title": "Empty Child Source",
            "source_type": "markdown",
            "trust_level": "official",
        },
    ).json()

    assert client.get(f"/products/{product['id']}/aliases").json() == []
    assert client.get(f"/sources/{source['id']}/versions").json() == []

    ask_payload = client.post(
        "/ask",
        json={"product_id": product["id"], "question": "Do empty child endpoints distinguish parents?"},
    ).json()
    question_id = ask_payload["question"]["id"]
    retrieval_run_id = ask_payload["retrieval_run"]["id"]
    assert client.get(f"/questions/{question_id}/attachments").json() == []
    assert client.get(f"/retrieval-runs/{retrieval_run_id}/candidates").json() == ask_payload["candidates"]

    eval_run = client.post("/eval-runs", json={"name": "empty eval"}).json()["eval_run"]
    assert client.get(f"/eval-runs/{eval_run['id']}/results").json() == []


def test_unsupported_embedding_provider_config_fails_ingestion_and_routes_review():
    client.post(
        "/provider-configs",
        json={
            "provider_type": "embedding",
            "provider_name": "openai",
            "model_name": "text-embedding-example",
            "config_json": {"api_key_env": "OPENAI_API_KEY"},
        },
    )
    product = client.post(
        "/products",
        json={"name": "Embedding Board", "slug": "embedding-board", "description": ""},
    ).json()
    source = client.post(
        "/sources",
        json={
            "product_id": product["id"],
            "title": "Embedding manual",
            "source_type": "markdown",
            "trust_level": "official",
        },
    ).json()

    payload = client.post(
        f"/sources/{source['id']}/versions",
        json={"version_label": "v1", "content": "USB power is configuration only."},
    ).json()

    assert payload["version"]["status"] == "failed"
    assert "Embedding provider 'openai' is configured but no adapter is installed." == payload["version"]["error_message"]
    assert payload["chunks"] == []
    assert payload["review_item"]["source_type"] == "source_issue"
    assert payload["review_item"]["failure_category"] == "bad_parse"
    assert client.get(f"/source-versions/{payload['version']['id']}/chunks").json() == []

    ask_payload = client.post(
        "/ask",
        json={"product_id": product["id"], "question": "What does USB power do?"},
    ).json()
    assert ask_payload["evidence"] == []


def test_failed_source_version_ingestion_saves_error_reason(monkeypatch):
    import app.sources.service as source_service

    product = client.post(
        "/products",
        json={"name": "FlyingRC F7", "slug": "flyingrc-f7", "description": "Flight controller"},
    ).json()
    source = client.post(
        "/sources",
        json={
            "product_id": product["id"],
            "title": "Broken import",
            "source_type": "markdown",
            "trust_level": "official",
        },
    ).json()

    def fail_ingestion(_store, _source_version_id):
        raise RuntimeError("parser failed on malformed source")

    monkeypatch.setattr(source_service, "ingest_source_version", fail_ingestion)
    response = client.post(
        f"/sources/{source['id']}/versions",
        json={"version_label": "broken", "content": "This import should be recorded as failed."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["version"]["status"] == "failed"
    assert payload["version"]["error_message"] == "parser failed on malformed source"
    assert payload["version"]["updated_at"] != payload["version"]["created_at"]
    assert payload["chunks"] == []
    assert payload["review_item"]["source_type"] == "source_issue"
    assert payload["review_item"]["failure_category"] == "bad_parse"
    assert "parser failed on malformed source" in payload["review_item"]["reviewer_notes"]
    version = client.get(f"/sources/{source['id']}/versions").json()[0]
    assert version["status"] == "failed"
    assert version["error_message"] == "parser failed on malformed source"
    review_items = client.get("/review-items").json()
    assert review_items[0]["id"] == payload["review_item"]["id"]


def test_failed_support_import_ingestion_creates_source_issue_review_items(monkeypatch):
    import app.sources.service as source_service

    product = client.post(
        "/products",
        json={"name": "Support Import Board", "slug": "support-import-board", "description": ""},
    ).json()
    image_payload = client.post(
        "/image-assets",
        json={
            "product_id": product["id"],
            "storage_uri": "local://support-import.png",
            "image_type": "wiring_photo",
        },
    ).json()

    def fail_ingestion(_store, _source_version_id):
        raise RuntimeError("support import parser failed")

    monkeypatch.setattr(source_service, "ingest_source_version", fail_ingestion)

    ticket_payload = client.post(
        "/tickets",
        json={
            "product_id": product["id"],
            "external_id": "T-500",
            "title": "Failed ticket import",
            "body": "This ticket body should still create a failed SourceVersion.",
        },
    ).json()
    assert ticket_payload["version"]["status"] == "failed"
    assert ticket_payload["chunks"] == []
    assert ticket_payload["review_item"]["source_type"] == "source_issue"
    assert ticket_payload["review_item"]["failure_category"] == "bad_parse"

    log_payload = client.post(
        "/log-sources",
        json={
            "product_id": product["id"],
            "log_type": "boot",
            "content": "BOOT_PARSE_FAILURE",
        },
    ).json()
    assert log_payload["version"]["status"] == "failed"
    assert log_payload["review_item"]["source_type"] == "source_issue"
    assert log_payload["review_item"]["failure_category"] == "bad_parse"

    ocr_payload = client.post(
        f"/image-assets/{image_payload['image_asset']['id']}/ocr",
        json={"ocr_text": "OCR_PARSE_FAILURE", "confidence": 0.5},
    ).json()
    assert ocr_payload["version"]["status"] == "failed"
    assert ocr_payload["review_item"]["source_type"] == "source_issue"
    assert ocr_payload["review_item"]["failure_category"] == "bad_parse"


def test_unsupported_ocr_provider_config_records_failed_result_and_routes_review():
    product = client.post(
        "/products",
        json={"name": "OCR Board", "slug": "ocr-board", "description": ""},
    ).json()
    client.post(
        "/provider-configs",
        json={
            "provider_type": "ocr",
            "provider_name": "vision-api",
            "model_name": "ocr-example",
            "config_json": {"api_key_env": "VISION_API_KEY"},
        },
    )
    image_payload = client.post(
        "/image-assets",
        json={
            "product_id": product["id"],
            "storage_uri": "local://ocr-board.png",
            "image_type": "wiring_photo",
        },
    ).json()

    ocr_payload = client.post(
        f"/image-assets/{image_payload['image_asset']['id']}/ocr",
        json={"ocr_text": "This manual OCR text should not be labeled as provider output.", "confidence": 0.8},
    ).json()

    assert ocr_payload["ocr_result"]["provider_name"] == "vision-api"
    assert ocr_payload["ocr_result"]["model_name"] == "ocr-example"
    assert ocr_payload["ocr_result"]["status"] == "failed"
    assert ocr_payload["ocr_result"]["ocr_text"] == ""
    assert ocr_payload["ocr_result"]["confidence"] == 0.0
    assert "no adapter is installed" in ocr_payload["ocr_result"]["error_message"]
    assert ocr_payload["version"] is None
    assert ocr_payload["chunks"] == []
    assert ocr_payload["review_item"]["source_type"] == "source_issue"
    assert ocr_payload["review_item"]["failure_category"] == "generation_error"
    ocr_results = client.get(f"/image-assets/{image_payload['image_asset']['id']}/ocr-results").json()
    assert ocr_results[0]["id"] == ocr_payload["ocr_result"]["id"]
    assert ocr_results[0]["status"] == "failed"


def test_ocr_result_history_requires_existing_image_asset():
    response = client.get(f"/image-assets/{uuid4()}/ocr-results")
    assert response.status_code == 404


def test_source_disable_removes_chunks_from_retrieval_and_is_audited():
    product, source, chunks = seed_source()
    before = client.post(
        "/ask",
        json={"product_id": product["id"], "question": "Can USB power servos?"},
    ).json()
    assert before["evidence"]

    disabled = client.post(
        f"/sources/{source['id']}/disable",
        json={"reason": "stale pinout"},
        headers={"X-BoardPilot-User": "maintainer-1", "X-BoardPilot-Role": "support"},
    )
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "disabled"
    assert disabled.json()["updated_at"] != source["updated_at"]
    after = client.post(
        "/ask",
        json={"product_id": product["id"], "question": "Can USB power servos?"},
    ).json()
    assert after["evidence"] == []
    audit_logs = client.get("/audit-logs").json()
    audit = [log for log in audit_logs if log["action"] == "source_disabled"]
    assert audit[-1]["user_id"] == "maintainer-1"
    assert audit[-1]["after_json"]["reason"] == "stale pinout"
    assert audit[-1]["after_json"]["disabled_chunk_count"] == len(chunks)


def test_product_and_source_patch_refresh_updated_at():
    product, source, _chunks = seed_source()
    patched_product = client.patch(
        f"/products/{product['id']}",
        json={"description": "Updated product description"},
        headers={"X-BoardPilot-Role": "admin"},
    ).json()
    assert patched_product["description"] == "Updated product description"
    assert patched_product["updated_at"] != product["updated_at"]

    patched_source = client.patch(
        f"/sources/{source['id']}",
        json={"trust_level": "verified"},
        headers={"X-BoardPilot-Role": "support"},
    ).json()
    assert patched_source["trust_level"] == "verified"
    assert patched_source["updated_at"] != source["updated_at"]


def test_patch_endpoints_ignore_immutable_fields():
    product, source, chunks = seed_source()
    other_product = client.post(
        "/products",
        json={"name": "Other Board", "slug": "other-board", "description": ""},
    ).json()
    malicious_id = str(uuid4())

    patched_product = client.patch(
        f"/products/{product['id']}",
        json={"id": malicious_id, "created_at": "2000-01-01T00:00:00", "description": "Still mutable"},
    ).json()
    assert patched_product["id"] == product["id"]
    assert patched_product["created_at"] == product["created_at"]
    assert patched_product["description"] == "Still mutable"

    patched_source = client.patch(
        f"/sources/{source['id']}",
        json={"id": malicious_id, "product_id": other_product["id"], "title": "Mutable source title"},
    ).json()
    assert patched_source["id"] == source["id"]
    assert patched_source["product_id"] == product["id"]
    assert patched_source["title"] == "Mutable source title"

    case = client.post(
        "/eval-cases",
        json={
            "product_id": product["id"],
            "question_text": "Initial immutable field check",
            "expected_chunk_ids_json": [chunks[0]["id"]],
        },
    ).json()
    patched_case = client.patch(
        f"/eval-cases/{case['id']}",
        json={"id": malicious_id, "created_at": "2000-01-01T00:00:00", "difficulty": "hard"},
    ).json()
    assert patched_case["id"] == case["id"]
    assert patched_case["created_at"] == case["created_at"]
    assert patched_case["difficulty"] == "hard"


def test_source_version_disable_removes_chunks_from_retrieval_and_is_audited():
    product, source, chunks = seed_source()
    source_versions = client.get(f"/sources/{source['id']}/versions").json()
    version_id = source_versions[0]["id"]
    before_updated_at = source_versions[0]["updated_at"]

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
    assert disabled["version"]["updated_at"] != before_updated_at
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
    before_updated_at = source_versions[0]["updated_at"]

    created = client.post("/ingestion/jobs", json={"source_version_id": version_id}).json()
    job = created["job"]
    assert job["status"] == "completed"
    assert job["source_version_id"] == version_id
    assert job["chunk_count"] == 0
    version_after_job = client.get(f"/sources/{source['id']}/versions").json()[0]
    assert version_after_job["status"] == "ingested"
    assert version_after_job["updated_at"] != before_updated_at

    listed = client.get("/ingestion/jobs").json()
    assert listed[0]["id"] == job["id"]

    fetched = client.get(f"/ingestion/jobs/{job['id']}").json()
    assert fetched["status"] == "completed"

    retried = client.post(f"/ingestion/jobs/{job['id']}/retry").json()
    assert retried["job"]["id"] == job["id"]
    assert retried["job"]["status"] == "completed"
    version_after_retry = client.get(f"/sources/{source['id']}/versions").json()[0]
    assert version_after_retry["updated_at"] != version_after_job["updated_at"]


def test_failed_ingestion_job_saves_source_version_error(monkeypatch):
    import app.ingestion.jobs as ingestion_jobs

    _product, source, _chunks = seed_source()
    before_version = client.get(f"/sources/{source['id']}/versions").json()[0]
    version_id = before_version["id"]

    def fail_ingestion(_store, _source_version_id):
        raise RuntimeError("embedding provider unavailable")

    monkeypatch.setattr(ingestion_jobs, "ingest_source_version", fail_ingestion)
    payload = client.post("/ingestion/jobs", json={"source_version_id": version_id}).json()

    assert payload["job"]["status"] == "failed"
    assert payload["job"]["error_message"] == "embedding provider unavailable"
    assert payload["chunks"] == []
    assert payload["review_item"]["source_type"] == "source_issue"
    assert payload["review_item"]["failure_category"] == "bad_parse"
    version = client.get(f"/sources/{source['id']}/versions").json()[0]
    assert version["status"] == "failed"
    assert version["error_message"] == "embedding provider unavailable"
    assert version["updated_at"] != before_version["updated_at"]


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


def test_pdf_upload_without_extractable_text_fails_and_routes_review(tmp_path, monkeypatch):
    import app.sources.service as source_service

    monkeypatch.setattr(source_service.settings, "storage_root", str(tmp_path))
    product, source, _chunks = seed_source(source_type="pdf", title="FlyingRC PDF Manual")
    response = client.post(
        f"/sources/{source['id']}/versions/upload",
        data={"version_label": "broken-pdf"},
        files={"file": ("broken.pdf", b"%PDF-1.4\nnot a readable pdf body", "application/pdf")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["version"]["status"] == "failed"
    assert "PDF text extraction failed" in payload["version"]["error_message"]
    assert payload["chunks"] == []
    assert payload["review_item"]["source_type"] == "source_issue"
    assert payload["review_item"]["failure_category"] == "bad_parse"


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


def test_csv_faq_upload_handles_common_export_headers_and_headerless_rows(tmp_path, monkeypatch):
    import app.sources.service as source_service

    monkeypatch.setattr(source_service.settings, "storage_root", str(tmp_path))
    _product, source, _chunks = seed_source(source_type="csv_faq", title="FlyingRC FAQ")
    response = client.post(
        f"/sources/{source['id']}/versions/upload",
        data={"version_label": "faq-export"},
        files={
            "file": (
                "faq-export.csv",
                "\ufeffQuestion Text,Resolution,Tags\n Can USB run servos? , No. Use USB for configuration only. , power\n".encode(),
                "text/csv",
            )
        },
    )
    payload = response.json()
    chunk_text = payload["chunks"][0]["content"]
    assert "Question: Can USB run servos?" in chunk_text
    assert "Answer: No. Use USB for configuration only." in chunk_text
    assert "Tags: power" in chunk_text

    headerless = client.post(
        f"/sources/{source['id']}/versions/upload",
        data={"version_label": "faq-headerless"},
        files={"file": ("faq-headerless.csv", b"Can USB power motors?,No,field note\n", "text/csv")},
    ).json()
    assert "Question: Can USB power motors?" in headerless["chunks"][0]["content"]
    assert "Answer: No" in headerless["chunks"][0]["content"]
    assert "Context: field note" in headerless["chunks"][0]["content"]


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


def test_webpage_snapshot_import_extracts_visible_text_and_metadata():
    product = client.post(
        "/products",
        json={"name": "FlyingRC F4", "slug": "flyingrc-f4", "description": "Flight controller"},
    ).json()
    source = client.post(
        "/sources",
        json={
            "product_id": product["id"],
            "title": "FlyingRC F4 Web Manual",
            "source_type": "webpage",
            "trust_level": "official",
        },
    ).json()
    response = client.post(
        f"/sources/{source['id']}/versions/webpage",
        json={
            "url": "https://example.com/flyingrc-f4",
            "version_label": "web-2026-05-20",
            "html": (
                "<html><head><title>FlyingRC F4</title><style>.x{}</style></head>"
                "<body><h1>USB_WEB_SNAPSHOT</h1><p>USB is for configuration only.</p>"
                "<script>throw new Error('ignore me')</script></body></html>"
            ),
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["version"]["parser_version"] == "mvp-webpage-parser-v1"
    assert payload["artifact"]["artifact_type"] == "webpage_snapshot"
    assert payload["artifact"]["storage_uri"] == "https://example.com/flyingrc-f4"
    assert payload["artifact"]["metadata_json"]["snapshot_url"] == "https://example.com/flyingrc-f4"
    chunk_text = payload["chunks"][0]["content"]
    assert "USB_WEB_SNAPSHOT" in chunk_text
    assert "USB is for configuration only." in chunk_text
    assert "throw new Error" not in chunk_text

    updated_source = client.get(f"/sources/{source['id']}").json()
    assert updated_source["canonical_uri"] == "https://example.com/flyingrc-f4"
    ask_payload = client.post(
        "/ask",
        json={"product_id": product["id"], "question": "What is USB_WEB_SNAPSHOT?"},
    ).json()
    assert any("USB_WEB_SNAPSHOT" in item["quote"] for item in ask_payload["evidence"])


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
    stages = {candidate["stage"] for candidate in payload["candidates"]}
    assert {"keyword", "vector", "merged", "reranked"} <= stages

    model_run = client.get(f"/model-runs/{payload['answer']['model_run_id']}").json()
    assert model_run["provider_type"] == "llm"
    assert model_run["provider_name"] == "fake"
    assert model_run["status"] == "completed"
    assert model_run["token_usage_json"]["output_words"] > 0

    evidence_ids = {item["id"] for item in payload["evidence"]}
    cited_ids = {ids[0] for ids in payload["answer"]["citation_map_json"].values()}
    assert cited_ids <= evidence_ids


def test_uncited_answer_routes_to_review_as_unsupported_claim(monkeypatch):
    import app.answers.service as answer_service
    from app.providers.base import LLMResult

    product, _source, _chunks = seed_source()

    def answer_without_visible_citation(_question, _evidence_quotes):
        return LLMResult("fake", "fake-citation-llm", 0, answer_text="USB power is for configuration only.")

    monkeypatch.setattr(answer_service.llm_provider, "answer", answer_without_visible_citation)
    payload = client.post(
        "/ask",
        json={"product_id": product["id"], "question": "Can I power servos from the USB connector?"},
    ).json()

    assert payload["evidence"]
    assert payload["answer"]["status"] == "unsupported_claim_risk"
    assert payload["answer"]["citation_map_json"] == {}
    assert payload["answer"]["confidence"] <= 0.2
    assert payload["review_item"]["failure_category"] == "unsupported_claim"


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


def test_ask_can_attach_existing_artifacts_during_submission():
    product, source, _chunks = seed_source()
    version_id = client.get(f"/sources/{source['id']}/versions").json()[0]["id"]
    artifact = client.get(f"/source-versions/{version_id}/artifacts").json()[0]
    ask_payload = client.post(
        "/ask",
        json={
            "product_id": product["id"],
            "question": "Can USB power servos if a log is attached?",
            "attachments": [
                {"artifact_id": artifact["id"], "attachment_type": "log", "description": "boot log copied from support case"}
            ],
        },
    ).json()

    assert ask_payload["attachments"][0]["artifact_id"] == artifact["id"]
    assert ask_payload["attachments"][0]["description"] == "boot log copied from support case"
    attachments = client.get(f"/questions/{ask_payload['question']['id']}/attachments").json()
    assert attachments[0]["id"] == ask_payload["attachments"][0]["id"]

    feedback = client.post(
        f"/answers/{ask_payload['answer']['id']}/feedback",
        json={"feedback_type": "needs_review", "notes": "inspect attached log"},
    ).json()
    detail = client.get(f"/review-items/{feedback['id']}/detail").json()
    assert detail["attachments"][0]["id"] == ask_payload["attachments"][0]["id"]


def test_ask_attachment_content_expands_retrieval_query():
    product = client.post(
        "/products",
        json={"name": "Attachment Board", "slug": "attachment-board", "description": ""},
    ).json()
    manual_source = client.post(
        "/sources",
        json={
            "product_id": product["id"],
            "title": "Attachment Board alarms",
            "source_type": "markdown",
            "trust_level": "official",
        },
    ).json()
    client.post(
        f"/sources/{manual_source['id']}/versions",
        json={
            "version_label": "v1",
            "content": "ALRM-773 means the CAN-FD harness has reversed telemetry wiring.",
        },
    )
    log_source = client.post(
        "/sources",
        json={
            "product_id": product["id"],
            "title": "Customer boot log",
            "source_type": "text_log",
            "trust_level": "customer",
        },
    ).json()
    log_version = client.post(
        f"/sources/{log_source['id']}/versions",
        json={"version_label": "log", "content": "Boot log excerpt: ALRM-773 during startup."},
    ).json()
    artifact = log_version["artifact"]

    ask_payload = client.post(
        "/ask",
        json={
            "product_id": product["id"],
            "question": "What does the attached alarm mean?",
            "attachments": [
                {
                    "artifact_id": artifact["id"],
                    "attachment_type": "log",
                    "description": "customer startup log",
                }
            ],
        },
    ).json()

    assert "alrm-773" in ask_payload["question"]["normalized_text"]
    evidence_text = "\n".join(item["quote"].lower() for item in ask_payload["evidence"])
    assert "alrm-773" in evidence_text
    assert ask_payload["attachments"][0]["artifact_id"] == artifact["id"]


def test_ask_persists_metadata_filters():
    payload = client.post(
        "/ask",
        json={"question": "Filter this query", "metadata_filters_json": {"firmware": "1.0", "page": 3}},
    ).json()
    assert payload["question"]["metadata_filters_json"] == {"firmware": "1.0", "page": 3}


def test_ask_metadata_filters_limit_retrieval_candidates():
    product, source, chunks = seed_source()
    normal_source = client.post(
        "/sources",
        json={
            "product_id": product["id"],
            "title": "Unofficial notes",
            "source_type": "markdown",
            "trust_level": "normal",
        },
    ).json()
    normal_version = client.post(
        f"/sources/{normal_source['id']}/versions",
        json={"version_label": "v1", "content": "USB power can run a bench servo in unofficial testing."},
    ).json()
    official_chunk_ids = {chunk["id"] for chunk in chunks}
    normal_chunk_ids = {chunk["id"] for chunk in normal_version["chunks"]}

    payload = client.post(
        "/ask",
        json={
            "product_id": product["id"],
            "question": "Can USB power servos?",
            "metadata_filters_json": {"trust_level": "official"},
        },
    ).json()

    candidate_chunk_ids = {candidate["chunk_id"] for candidate in payload["candidates"]}
    assert candidate_chunk_ids
    assert candidate_chunk_ids <= official_chunk_ids
    assert candidate_chunk_ids.isdisjoint(normal_chunk_ids)
    assert {
        "type": "hard_filter",
        "field": "trust_level",
        "value": "official",
    } in payload["retrieval_run"]["filter_plan_json"]["filters"]


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


def test_high_confidence_product_alias_uses_hard_filter():
    product, _source, chunks = seed_source()
    client.post(
        f"/products/{product['id']}/aliases",
        json={"alias": "F4 FC", "alias_type": "user_facing", "confidence": 0.99},
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
    other_version = client.post(
        f"/sources/{other_source['id']}/versions",
        json={"version_label": "v1", "content": "USB power on this board has unrelated constraints."},
    ).json()

    payload = client.post("/ask", json={"question": "For the F4 FC, can USB power servos?"}).json()
    filters = payload["retrieval_run"]["filter_plan_json"]["filters"]
    candidate_chunk_ids = {candidate["chunk_id"] for candidate in payload["candidates"]}

    assert filters[0]["type"] == "hard_filter"
    assert filters[0]["value"] == product["id"]
    assert filters[0]["source"] == "detected_entity"
    assert candidate_chunk_ids <= {chunk["id"] for chunk in chunks}
    assert candidate_chunk_ids.isdisjoint({chunk["id"] for chunk in other_version["chunks"]})


def test_ask_detects_hardware_entities():
    product, _source, _chunks = seed_source()
    client.post(
        f"/products/{product['id']}/aliases",
        json={"alias": "F4 FC", "alias_type": "user_facing", "confidence": 0.82},
    )

    payload = client.post(
        "/ask",
        json={"question": "F4 FC on PX4 v1.14.3 shows ERR-42 on M1 with USB-C and CAN-FD connected."},
    ).json()
    entities = payload["question"]["detected_entities_json"]

    assert entities["products"][0]["product_id"] == product["id"]
    assert "PX4 v1.14.3" in entities["firmware_versions"]
    assert "ERR-42" in entities["error_codes"]
    assert "M1" in entities["connectors"]
    assert "USB-C" in entities["connectors"]
    assert "CAN-FD" in entities["interfaces"]


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
    assert payload["answer"]["status"] == "insufficient_evidence"
    assert payload["answer"]["evidence_sufficiency"] == "insufficient"
    assert payload["answer"]["confidence"] == 0.0
    assert payload["answer"]["citation_map_json"] == {}
    assert payload["review_item"]["status"] == "open"
    model_run = client.get(f"/model-runs/{payload['answer']['model_run_id']}").json()
    assert model_run["status"] == "skipped"
    assert model_run["error_message"] == "insufficient evidence"
    assert model_run["cost_json"]["total_cost"] == 0.0


def test_partial_evidence_answer_uses_explicit_status_and_review_route():
    product = client.post(
        "/products",
        json={"name": "FlyingRC Mini", "slug": "flyingrc-mini", "description": "Small flight controller"},
    ).json()
    source = client.post(
        "/sources",
        json={
            "product_id": product["id"],
            "title": "FlyingRC Mini Note",
            "source_type": "markdown",
            "trust_level": "official",
        },
    ).json()
    client.post(
        f"/sources/{source['id']}/versions",
        json={"version_label": "v1", "content": "The FlyingRC Mini supports CAN-FD on connector J3."},
    )

    payload = client.post(
        "/ask",
        json={"product_id": product["id"], "question": "Which connector supports CAN-FD on the FlyingRC Mini?"},
    ).json()

    assert payload["answer"]["status"] == "partial_evidence"
    assert payload["answer"]["evidence_sufficiency"] == "partial"
    assert len(payload["evidence"]) == 1
    assert payload["review_item"]["source_type"] == "low_confidence_answer"
    assert payload["review_item"]["failure_category"] == "insufficient_evidence"
    assert payload["review_item"]["priority"] == 2


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
    assert feedback.json()["source_type"] == "source_issue"
    assert feedback.json()["failure_category"] == "missing_source"
    assert feedback.json()["priority"] == 1
    assert feedback.json()["answer_id"] == ask_payload["answer"]["id"]
    assert feedback.json()["reviewer_notes"] == "Need a stronger source citation."

    incorrect = client.post(
        f"/answers/{ask_payload['answer']['id']}/feedback",
        json={"feedback_type": "incorrect", "notes": "Answer includes an unsupported claim."},
    ).json()
    assert incorrect["source_type"] == "user_feedback"
    assert incorrect["failure_category"] == "unsupported_claim"
    assert incorrect["priority"] == 1

    helpful = client.post(
        f"/answers/{ask_payload['answer']['id']}/feedback",
        json={"feedback_type": "helpful", "notes": "This resolved my issue."},
    ).json()
    assert helpful["source_type"] == "user_feedback"
    assert helpful["failure_category"] is None
    assert helpful["status"] == "approved"
    assert helpful["priority"] == 4
    active_review_ids = [item["id"] for item in client.get("/review-items").json()]
    all_review_ids = [item["id"] for item in client.get("/review-items?status=all").json()]
    assert helpful["id"] not in active_review_ids
    assert helpful["id"] in all_review_ids


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


def test_unsupported_llm_provider_config_records_failed_model_run_and_routes_review():
    product, _source, _chunks = seed_source()
    client.post(
        "/provider-configs",
        json={
            "provider_type": "llm",
            "provider_name": "openai",
            "model_name": "gpt-example",
            "config_json": {"api_key_env": "OPENAI_API_KEY"},
        },
    )

    payload = client.post(
        "/ask",
        json={"product_id": product["id"], "question": "Can I power servos from USB?"},
    ).json()

    assert payload["answer"]["status"] == "generation_error"
    assert payload["answer"]["provider_name"] == "openai"
    assert payload["answer"]["model_name"] == "gpt-example"
    assert payload["answer"]["confidence"] == 0.0
    assert payload["review_item"]["source_type"] == "generation_error"
    assert payload["review_item"]["failure_category"] == "generation_error"
    model_run = client.get(f"/model-runs/{payload['answer']['model_run_id']}").json()
    assert model_run["status"] == "failed"
    assert "no adapter is installed" in model_run["error_message"]


def test_unsupported_reranker_provider_config_degrades_retrieval_and_routes_review():
    product, _source, _chunks = seed_source()
    client.post(
        "/provider-configs",
        json={
            "provider_type": "reranker",
            "provider_name": "cohere",
            "model_name": "rerank-example",
            "config_json": {"api_key_env": "COHERE_API_KEY"},
        },
    )

    payload = client.post(
        "/ask",
        json={"product_id": product["id"], "question": "Can I power servos from USB?"},
    ).json()

    assert payload["retrieval_run"]["status"] == "completed_with_reranker_error"
    assert "Reranker provider 'cohere' is configured but no adapter is installed." == payload["retrieval_run"]["error_message"]
    reranked = [candidate for candidate in payload["candidates"] if candidate["stage"] == "reranked"]
    assert reranked
    assert reranked[0]["source"] == "fallback_merged"
    assert reranked[0]["metadata_json"]["reranker_configured_provider_name"] == "cohere"
    assert reranked[0]["metadata_json"]["reranker_model_name"] == "rerank-example"
    assert payload["review_item"]["source_type"] == "retrieval_issue"
    assert payload["review_item"]["failure_category"] == "bad_rerank"


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
    assert "eval_duration_ms" in eval_run["summary_metrics_json"]
    assert eval_run["retrieval_config_json"] == {"keyword_limit": 50, "vector_limit": 50, "evidence_limit": 5}
    assert eval_run["provider_config_json"]["llm"]["model_name"] == "fake-citation-llm-costed"
    assert eval_run["summary_metrics_json"]["model_cost"] > 0
    assert results[0]["eval_case_id"] == case["id"]

    review = client.post(f"/eval-results/{results[0]['id']}/to-review").json()
    assert review["source_type"] == "eval_failure"


def test_eval_run_categorizes_insufficient_evidence_failures_for_review():
    product = client.post(
        "/products",
        json={"name": "No Source Board", "slug": "no-source-board", "description": "No source content yet"},
    ).json()
    client.post(
        "/eval-cases",
        json={
            "product_id": product["id"],
            "question_text": "What evidence exists for this board?",
            "expected_answer_points_json": ["Should require saved evidence"],
            "tags_json": ["missing_source"],
        },
    )

    run_payload = client.post("/eval-runs", json={"name": "missing source eval"}).json()
    result = run_payload["results"][0]
    assert result["need_review"] is True
    assert result["failure_category"] == "insufficient_evidence"
    assert run_payload["eval_run"]["summary_metrics_json"]["failure_category_distribution"] == {"insufficient_evidence": 1}

    review = client.post(f"/eval-results/{result['id']}/to-review").json()
    assert review["source_type"] == "eval_failure"
    assert review["failure_category"] == "insufficient_evidence"


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

    faq_payload = client.post(
        f"/review-items/{review_item['id']}/to-faq",
        headers={"X-BoardPilot-User": "reviewer-faq", "X-BoardPilot-Role": "reviewer"},
    ).json()
    assert faq_payload["status"] == "converted_to_faq"
    assert faq_payload["approved_faq"]["question_text"].startswith("What is the secret")
    assert faq_payload["approved_faq"]["answer_text"].startswith("Use the documented calibration")
    assert faq_payload["source"]["source_type"] == "approved_faq"
    assert faq_payload["chunks"]
    converted_item = client.get(f"/review-items/{review_item['id']}").json()
    assert converted_item["status"] == "converted_to_faq"
    assert converted_item["reviewer_id"] == "reviewer-faq"
    assert converted_item["updated_at"] != review_item["updated_at"]
    audit_logs = client.get("/audit-logs").json()
    faq_audit = [log for log in audit_logs if log["action"] == "review_converted_to_faq"]
    assert faq_audit[-1]["user_id"] == "reviewer-faq"

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

    eval_case = client.post(
        f"/review-items/{review_item['id']}/to-eval-case",
        headers={"X-BoardPilot-User": "reviewer-eval", "X-BoardPilot-Role": "reviewer"},
    ).json()
    assert eval_case["question_text"] == "Can I power servos from USB?"
    assert eval_case["expected_chunk_ids_json"]
    assert eval_case["expected_source_ids_json"]
    assert eval_case["expected_answer_points_json"][0].startswith("USB is for configuration")
    assert "review_regression" in eval_case["tags_json"]
    converted_item = client.get(f"/review-items/{review_item['id']}").json()
    assert converted_item["status"] == "converted_to_eval_case"
    assert converted_item["reviewer_id"] == "reviewer-eval"
    assert converted_item["updated_at"] != review_item["updated_at"]
    audit_logs = client.get("/audit-logs").json()
    eval_audit = [log for log in audit_logs if log["action"] == "review_converted_to_eval_case"]
    assert eval_audit[-1]["user_id"] == "reviewer-eval"


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

    invalid_category = client.post(
        f"/review-items/{review_item['id']}/approve",
        json={"failure_category": "not_a_failure_category"},
    )
    assert invalid_category.status_code == 422
    assert invalid_category.json()["detail"] == "invalid failure_category"

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
    assert approved.json()["updated_at"] != patched.json()["updated_at"]
    audit_actions = [item["action"] for item in client.get("/audit-logs").json()]
    assert "review_item_updated" in audit_actions

    audit_logs = client.get("/audit-logs").json()
    review_audit = [log for log in audit_logs if log["action"] == "review_approved"]
    assert review_audit
    assert review_audit[-1]["user_id"] == "reviewer-1"
    assert review_audit[-1]["entity_id"] == review_item["id"]
    assert review_audit[-1]["before_json"]["status"] == patched.json()["status"]
    assert review_audit[-1]["after_json"]["status"] == "approved"

    active_items = client.get("/review-items").json()
    all_items = client.get("/review-items?status=all").json()
    approved_items = client.get("/review-items?status=approved").json()
    assert review_item["id"] not in [item["id"] for item in active_items]
    assert review_item["id"] in [item["id"] for item in all_items]
    assert review_item["id"] in [item["id"] for item in approved_items]
    assert client.get("/review-items?status=not_a_status").status_code == 422


def test_review_reject_requires_failure_category_and_is_audited():
    ask_payload = client.post("/ask", json={"question": "What should be rejected?"}).json()
    review_item = ask_payload["review_item"]

    missing_category = client.post(f"/review-items/{review_item['id']}/reject", json={})
    assert missing_category.status_code == 422
    assert "failure_category" in missing_category.json()["detail"]

    invalid_category = client.post(
        f"/review-items/{review_item['id']}/reject",
        json={"failure_category": "not_a_failure_category"},
    )
    assert invalid_category.status_code == 422
    assert invalid_category.json()["detail"] == "invalid failure_category"

    rejected = client.post(
        f"/review-items/{review_item['id']}/reject",
        json={"failure_category": "unsupported_claim"},
        headers={"X-BoardPilot-User": "reviewer-3", "X-BoardPilot-Role": "reviewer"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["failure_category"] == "unsupported_claim"
    assert rejected.json()["updated_at"] != review_item["updated_at"]
    audit_logs = client.get("/audit-logs").json()
    review_audit = [log for log in audit_logs if log["action"] == "review_rejected"]
    assert review_audit
    assert review_audit[-1]["user_id"] == "reviewer-3"
    assert review_audit[-1]["entity_id"] == review_item["id"]
    assert review_audit[-1]["before_json"]["status"] == "open"
    assert review_audit[-1]["after_json"]["status"] == "rejected"


def test_review_can_be_marked_as_needing_source_update():
    ask_payload = client.post("/ask", json={"question": "What source needs updating?"}).json()
    review_item = ask_payload["review_item"]
    invalid_category = client.post(
        f"/review-items/{review_item['id']}/source-update-needed",
        json={"failure_category": "not_a_failure_category"},
    )
    assert invalid_category.status_code == 422
    assert invalid_category.json()["detail"] == "invalid failure_category"

    marked = client.post(
        f"/review-items/{review_item['id']}/source-update-needed",
        json={"failure_category": "stale_source"},
        headers={"X-BoardPilot-User": "reviewer-2", "X-BoardPilot-Role": "reviewer"},
    )
    assert marked.status_code == 200
    assert marked.json()["status"] == "needs_source_update"
    assert marked.json()["failure_category"] == "stale_source"
    assert marked.json()["updated_at"] != review_item["updated_at"]
    audit_logs = client.get("/audit-logs").json()
    source_update_audit = [log for log in audit_logs if log["action"] == "review_marked_source_update_needed"]
    assert source_update_audit
    assert source_update_audit[-1]["before_json"]["status"] == "open"
    assert source_update_audit[-1]["after_json"]["status"] == "needs_source_update"


def test_source_and_eval_case_changes_are_audit_logged():
    product, source, chunks = seed_source()
    client.patch(
        f"/sources/{source['id']}",
        json={"status": "disabled"},
        headers={"X-BoardPilot-User": "maintainer-1", "X-BoardPilot-Role": "support"},
    )
    after_disable = client.post(
        "/ask",
        json={"product_id": product["id"], "question": "Can USB power servos?"},
    ).json()
    assert after_disable["evidence"] == []
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
    source_disable_audit = [log for log in audit_logs if log["action"] == "source_disabled"]
    eval_audit = [log for log in audit_logs if log["action"] == "eval_case_modified"]
    assert source_audit[-1]["before_json"]["status"] == "active"
    assert source_audit[-1]["after_json"]["status"] == "disabled"
    assert source_audit[-1]["user_id"] == "maintainer-1"
    assert source_disable_audit[-1]["after_json"]["disabled_chunk_count"] == len(chunks)
    assert source_disable_audit[-1]["user_id"] == "maintainer-1"
    assert eval_audit[-1]["before_json"]["difficulty"] == "normal"
    assert eval_audit[-1]["after_json"]["difficulty"] == "hard"
