from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import logging_config
from app.main import app

CHAT_PAYLOAD = {
    "user_id": "student-01",
    "session_id": "session-01",
    "feature": "qa",
    "message": "Explain observability",
}
ENRICHMENT_FIELDS = {"user_id_hash", "session_id", "feature", "model", "env"}
GENERATED_ID = re.compile(r"req-[0-9a-f]{8}")


@pytest.fixture
def log_path(monkeypatch, tmp_path: Path) -> Path:
    path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", path)
    return path


def read_events(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_response_carries_correlation_headers(log_path: Path) -> None:
    with TestClient(app) as client:
        response = client.post("/chat", json=CHAT_PAYLOAD)

    assert response.status_code == 200
    correlation_id = response.headers["x-request-id"]
    assert GENERATED_ID.fullmatch(correlation_id)
    assert response.json()["correlation_id"] == correlation_id
    assert float(response.headers["x-response-time-ms"]) >= 0


def test_api_logs_carry_correlation_id_and_enrichment(log_path: Path) -> None:
    with TestClient(app) as client:
        response = client.post("/chat", json=CHAT_PAYLOAD)

    correlation_id = response.headers["x-request-id"]
    api_events = [event for event in read_events(log_path) if event.get("service") == "api"]

    assert {event["event"] for event in api_events} == {"request_received", "response_sent"}
    for event in api_events:
        assert event["correlation_id"] == correlation_id
        assert ENRICHMENT_FIELDS.issubset(event.keys())


def test_each_request_gets_a_distinct_correlation_id(log_path: Path) -> None:
    with TestClient(app) as client:
        first = client.post("/chat", json=CHAT_PAYLOAD)
        second = client.post("/chat", json=CHAT_PAYLOAD)

    assert first.headers["x-request-id"] != second.headers["x-request-id"]


def test_inbound_request_id_is_reused_only_when_safe(log_path: Path) -> None:
    with TestClient(app) as client:
        trusted = client.post(
            "/chat", json=CHAT_PAYLOAD, headers={"x-request-id": "req-upstream-01"}
        )
        rejected = client.post(
            "/chat", json=CHAT_PAYLOAD, headers={"x-request-id": "bad id with spaces"}
        )

    assert trusted.headers["x-request-id"] == "req-upstream-01"
    assert GENERATED_ID.fullmatch(rejected.headers["x-request-id"])


def test_inbound_request_id_shaped_like_pii_is_replaced(log_path: Path) -> None:
    # The correlation id bypasses the log scrubber, so an id carrying PII has to be
    # dropped here or it reaches data/logs.jsonl verbatim.
    pii_ids = ("0987654321", "123456789012", "4111-1111-1111-1111")

    with TestClient(app) as client:
        for pii_id in pii_ids:
            response = client.post(
                "/chat", json=CHAT_PAYLOAD, headers={"x-request-id": pii_id}
            )
            assert GENERATED_ID.fullmatch(response.headers["x-request-id"])

    logged = "\n".join(json.dumps(event) for event in read_events(log_path))
    for pii_id in pii_ids:
        assert pii_id not in logged
