from fastapi.testclient import TestClient

from app.core.rate_limit import rate_limiter
from app.core.security import mask_aadhaar, mask_pan
from app.main import app


client = TestClient(app)


def test_masks_sensitive_identifiers():
    assert mask_pan("ABCDE1234F") == "ABCDE****F"
    assert mask_aadhaar("123456789012") == "**** **** 9012"


def test_normalize_bad_pan_returns_400_without_echoing_sensitive_values():
    response = client.post(
        "/v1/normalize",
        json={
            "pan": "BADPAN",
            "aadhaar_number": "123456789012",
            "assessment_year": "2026-27",
            "entity_type": "individual",
            "residency_status": "resident",
        },
    )

    body = response.text
    assert response.status_code == 400
    assert "invalid_schema" in body
    assert "BADPAN" not in body
    assert "123456789012" not in body


def test_malformed_json_is_rejected_early():
    response = client.post(
        "/v1/normalize",
        content="{bad-json",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "malformed_json"


def test_injection_like_payload_is_rejected_early():
    response = client.post(
        "/v1/normalize",
        json={
            "pan": "ABCDE1234F",
            "assessment_year": "2026-27",
            "entity_type": "individual",
            "residency_status": "<script>alert(1)</script>",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"] == "invalid_payload"


def test_rate_limit_blocks_when_threshold_exceeded():
    previous_limit = rate_limiter.max_requests
    rate_limiter.max_requests = 2
    rate_limiter.clear()
    try:
        for index in range(3):
            response = client.get("/v1/health", headers={"X-Forwarded-For": "203.0.113.50"})
            if index < 2:
                assert response.status_code == 200
            else:
                assert response.status_code == 429
                assert response.json()["error"] == "rate_limited"
    finally:
        rate_limiter.max_requests = previous_limit
        rate_limiter.clear()
