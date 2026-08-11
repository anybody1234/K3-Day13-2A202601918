from __future__ import annotations

import hashlib

from app.logging_config import SYSTEM_FIELDS, scrub_event
from app.pii import hash_user_id


def scrub(event_dict: dict) -> dict:
    return scrub_event(None, "info", event_dict)


def test_system_fields_survive_scrubbing() -> None:
    # hash_user_id() returns 12 hex chars, so roughly one hash in 230 is all digits and
    # matches the cccd pattern. Redacting it would break the join key without any test
    # noticing, which is why these fields are exempt.
    event = {
        "ts": "2026-08-11T03:35:24Z",
        "level": "info",
        "service": "api",
        "env": "dev",
        "correlation_id": "req-a62c2c06",
        "user_id_hash": "094398086290",
        "model": "claude-sonnet-4-5",
        "error_type": "ValueError",
    }

    assert scrub(dict(event)) == event


def test_all_digit_user_hashes_are_not_redacted() -> None:
    digit_hashes = [
        h for i in range(20000) if (h := hash_user_id(str(i))).isdigit()
    ]
    assert digit_hashes, "expected the corpus to contain at least one all-digit hash"

    for user_hash in digit_hashes:
        assert scrub({"user_id_hash": user_hash})["user_id_hash"] == user_hash


def test_hash_user_id_stays_twelve_chars() -> None:
    # SYSTEM_FIELDS exempts user_id_hash on the assumption it is a hash, not user text.
    digest = hash_user_id("student-01")
    assert len(digest) == 12
    assert digest == hashlib.sha256(b"student-01").hexdigest()[:12]


def test_nested_payload_is_scrubbed_through_dicts_and_lists() -> None:
    event = {
        "event": "request_received",
        "payload": {
            "messages": ["mail a@b.vn", {"note": "goi 0901234567"}],
            "meta": {"card": "4111 1111 1111 1111"},
            "latency_ms": 142,
        },
    }

    payload = scrub(event)["payload"]

    assert payload["messages"][0] == "mail [REDACTED_EMAIL]"
    assert payload["messages"][1]["note"] == "goi [REDACTED_PHONE_VN]"
    assert payload["meta"]["card"] == "[REDACTED_CREDIT_CARD]"
    assert payload["latency_ms"] == 142


def test_caller_supplied_fields_are_still_scrubbed() -> None:
    # session_id and feature come straight off the request body, so they stay in scope.
    event = {"session_id": "0901234567", "feature": "mail a@b.vn"}

    scrubbed = scrub(event)

    assert scrubbed["session_id"] == "[REDACTED_PHONE_VN]"
    assert scrubbed["feature"] == "mail [REDACTED_EMAIL]"
    assert not SYSTEM_FIELDS & {"session_id", "feature", "payload", "event"}
