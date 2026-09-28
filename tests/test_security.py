"""
test_security.py - Unit Tests for Chunk 2 (Validator & Rate Limiter)
Part of BiscuitAI

Mental Model:
Verifies that:
  - Valid payloads pass cleanly through the validator.
  - Every category of bad input (wrong type, too long, bad pattern,
    unknown field, missing required field, disallowed value) is REJECTED
    with a clean ValidationError before any business logic runs.
  - Rate limiter correctly blocks after threshold is exceeded and
    resets after the time window expires.
  - IP extraction works correctly across all API Gateway event formats.
"""

import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from validator import (
    validate_request,
    build_validation_error_response,
    ValidationError
)
from rate_limiter import (
    check_rate_limit,
    extract_client_ip,
    get_rate_limit_headers,
    RATE_LIMIT_CONFIGS,
    _request_log   # Access internals only in tests for state reset
)


# ─── HELPER ──────────────────────────────────────────────────────────────────

def _reset_rate_limit_state():
    """Clear all in-memory rate limit tracking between tests."""
    _request_log.clear()


def _expect_validation_error(schema_key: str, payload: dict, expected_field: str):
    """Helper: assert that validate_request raises ValidationError on given field."""
    try:
        validate_request(schema_key, payload)
        assert False, f"Expected ValidationError on field '{expected_field}' but none was raised"
    except ValidationError as e:
        assert e.field == expected_field or expected_field in e.field, (
            f"Expected error on '{expected_field}', got error on '{e.field}': {e.message}"
        )


# ─── VALIDATOR: HAPPY PATH ────────────────────────────────────────────────────

def test_valid_forecast_payload():
    payload = {
        "store_id": "STR-001",
        "sku_id": "SKU-004",
        "festival_key": "DURGA_PUJA",
        "forecast_days": 7,
        "sales_history": [20, 22, 25, 28, 30, 31, 33]
    }
    result = validate_request("forecast", payload)
    assert result == payload  # Unchanged — no coercion
    print("PASS: test_valid_forecast_payload")


def test_valid_auto_po_payload():
    payload = {
        "store_id": "STR-003",
        "festival_key": "REGULAR",
        "sku_ids": ["SKU-001", "SKU-002", "SKU-003"]
    }
    result = validate_request("auto_po", payload)
    assert result == payload
    print("PASS: test_valid_auto_po_payload")


def test_valid_promotions_payload_with_optional_fields():
    payload = {
        "sku_name": "Biskfarm Marie Classic",
        "recommended_cartons": 15,
        "festival_key": "DIWALI",
        "language": "bn",
        "discount_pct": 5.0,
        "cutoff_day": "Thursday"
    }
    result = validate_request("promotions", payload)
    assert result == payload
    print("PASS: test_valid_promotions_payload_with_optional_fields")


def test_valid_promotions_payload_without_optional_fields():
    """Optional fields may be absent — must not cause a required-field error."""
    payload = {
        "sku_name": "Parle-G Gold",
        "recommended_cartons": 10,
        "festival_key": "REGULAR"
    }
    result = validate_request("promotions", payload)
    assert result == payload
    print("PASS: test_valid_promotions_payload_without_optional_fields")


# ─── VALIDATOR: TYPE REJECTION ────────────────────────────────────────────────

def test_reject_wrong_type_forecast_days():
    """forecast_days='7' (string) must be rejected — no coercion to int."""
    payload = {
        "store_id": "STR-001",
        "sku_id": "SKU-001",
        "festival_key": "REGULAR",
        "forecast_days": "7",      # ← String, not int
        "sales_history": [10, 12, 14]
    }
    _expect_validation_error("forecast", payload, "forecast_days")
    print("PASS: test_reject_wrong_type_forecast_days")


def test_reject_boolean_as_integer():
    """Python bool is a subclass of int — must be treated as wrong type for numeric fields."""
    payload = {
        "store_id": "STR-001",
        "sku_id": "SKU-001",
        "festival_key": "REGULAR",
        "forecast_days": True,     # ← bool, not int (even though isinstance(True, int) is True)
        "sales_history": [10, 12, 14]
    }
    # Bool guard is now fixed in _check_field() — True must be rejected, not accepted as int 1.
    _expect_validation_error("forecast", payload, "forecast_days")
    print("PASS: test_reject_boolean_as_integer")


# ─── VALIDATOR: RANGE REJECTION ───────────────────────────────────────────────

def test_reject_forecast_days_over_maximum():
    payload = {
        "store_id": "STR-001",
        "sku_id": "SKU-001",
        "festival_key": "REGULAR",
        "forecast_days": 91,       # ← Max is 90
        "sales_history": [10, 12, 14]
    }
    _expect_validation_error("forecast", payload, "forecast_days")
    print("PASS: test_reject_forecast_days_over_maximum")


def test_reject_zero_cartons():
    payload = {
        "sku_name": "Biskfarm Marie",
        "recommended_cartons": 0,  # ← Min is 1
        "festival_key": "REGULAR"
    }
    _expect_validation_error("promotions", payload, "recommended_cartons")
    print("PASS: test_reject_zero_cartons")


def test_reject_negative_discount():
    payload = {
        "sku_name": "Biskfarm Marie",
        "recommended_cartons": 5,
        "festival_key": "REGULAR",
        "discount_pct": -1.0       # ← Min is 0.0
    }
    _expect_validation_error("promotions", payload, "discount_pct")
    print("PASS: test_reject_negative_discount")


# ─── VALIDATOR: PATTERN REJECTION ─────────────────────────────────────────────

def test_reject_invalid_store_id_format():
    """store_id must match STR-\\d{3,6} — anything else is rejected."""
    payload = {
        "store_id": "STORE_001",   # ← Wrong pattern
        "festival_key": "REGULAR",
        "sku_ids": ["SKU-001"]
    }
    _expect_validation_error("auto_po", payload, "store_id")
    print("PASS: test_reject_invalid_store_id_format")


def test_reject_sql_injection_in_store_id():
    """SQL injection attempt in store_id must be rejected by pattern check."""
    payload = {
        "store_id": "STR-001; DROP TABLE inventory;",
        "festival_key": "REGULAR",
        "sku_ids": ["SKU-001"]
    }
    _expect_validation_error("auto_po", payload, "store_id")
    print("PASS: test_reject_sql_injection_in_store_id")


def test_reject_invalid_sku_id_in_list():
    """Each element of sku_ids must match SKU-\\d{3,6} pattern."""
    payload = {
        "store_id": "STR-001",
        "festival_key": "REGULAR",
        "sku_ids": ["SKU-001", "../../etc/passwd"]  # ← Path traversal attempt
    }
    _expect_validation_error("auto_po", payload, "sku_ids[1]")
    print("PASS: test_reject_invalid_sku_id_in_list")


# ─── VALIDATOR: ALLOWLIST REJECTION ───────────────────────────────────────────

def test_reject_unknown_festival_key():
    payload = {
        "store_id": "STR-001",
        "sku_id": "SKU-001",
        "festival_key": "CHRISTMAS",  # ← Not in allowed set
        "forecast_days": 7,
        "sales_history": [10, 12, 14]
    }
    _expect_validation_error("forecast", payload, "festival_key")
    print("PASS: test_reject_unknown_festival_key")


def test_reject_unknown_language():
    payload = {
        "sku_name": "Biskfarm Marie",
        "recommended_cartons": 5,
        "festival_key": "REGULAR",
        "language": "fr"           # ← French not in allowed set
    }
    _expect_validation_error("promotions", payload, "language")
    print("PASS: test_reject_unknown_language")


# ─── VALIDATOR: MISSING & EXTRA FIELD REJECTION ───────────────────────────────

def test_reject_missing_required_field():
    """Missing sales_history (required) must be rejected."""
    payload = {
        "store_id": "STR-001",
        "sku_id": "SKU-001",
        "festival_key": "REGULAR",
        "forecast_days": 7
        # sales_history is missing
    }
    _expect_validation_error("forecast", payload, "sales_history")
    print("PASS: test_reject_missing_required_field")


def test_reject_extra_unknown_field():
    """Extra fields not in schema must be rejected — strict allowlist."""
    payload = {
        "store_id": "STR-001",
        "sku_id": "SKU-001",
        "festival_key": "REGULAR",
        "forecast_days": 7,
        "sales_history": [10, 12, 14],
        "__proto__": "injected"     # ← Prototype pollution attempt
    }
    _expect_validation_error("forecast", payload, "body")
    print("PASS: test_reject_extra_unknown_field")


def test_reject_non_dict_body():
    """A JSON array or string as body must be rejected immediately."""
    try:
        validate_request("forecast", ["store_id", "SKU-001"])  # type: ignore
        assert False, "Should have raised ValidationError"
    except ValidationError as e:
        assert e.field == "body"
    print("PASS: test_reject_non_dict_body")


# ─── VALIDATOR: ERROR RESPONSE FORMAT ─────────────────────────────────────────

def test_validation_error_response_format():
    """Error response must never leak stack trace or internal paths."""
    try:
        validate_request("forecast", {"store_id": "bad!"})
    except ValidationError as e:
        response = build_validation_error_response(e)
        assert response["status"] == 400
        assert "error" in response
        assert "field" in response
        assert "detail" in response
        # Must NOT contain any of these leak indicators
        assert "Traceback" not in str(response)
        assert "lambda_function" not in str(response)
        assert "D:\\" not in str(response)
    print("PASS: test_validation_error_response_format")


# ─── RATE LIMITER TESTS ───────────────────────────────────────────────────────

def test_rate_limit_allows_within_limit():
    _reset_rate_limit_state()
    allowed, info = check_rate_limit("192.168.1.1", "forecast")
    assert allowed is True
    assert info == {}
    print("PASS: test_rate_limit_allows_within_limit")


def test_rate_limit_blocks_after_burst():
    """After burst_requests requests in BURST_WINDOW_SECONDS, next must be blocked."""
    _reset_rate_limit_state()
    ip = "10.0.0.5"
    endpoint = "forecast"
    burst_limit = RATE_LIMIT_CONFIGS[endpoint]["burst_requests"]  # 5

    # Send exactly burst_limit requests
    for i in range(burst_limit):
        allowed, _ = check_rate_limit(ip, endpoint)
        assert allowed, f"Request {i+1} should be allowed (burst limit is {burst_limit})"

    # Next request must be blocked
    allowed, info = check_rate_limit(ip, endpoint)
    assert allowed is False
    assert info["status"] == 429
    assert "retry_after" in info
    print("PASS: test_rate_limit_blocks_after_burst")


def test_rate_limit_different_ips_independent():
    """Two different IPs must have completely independent rate limit counters."""
    _reset_rate_limit_state()
    endpoint = "forecast"
    burst_limit = RATE_LIMIT_CONFIGS[endpoint]["burst_requests"]

    # Exhaust IP A
    for _ in range(burst_limit):
        check_rate_limit("1.1.1.1", endpoint)

    # IP B must still be allowed
    allowed, _ = check_rate_limit("2.2.2.2", endpoint)
    assert allowed is True
    print("PASS: test_rate_limit_different_ips_independent")


def test_rate_limit_different_endpoints_independent():
    """Hitting the rate limit on 'forecast' must not affect 'inventory'."""
    _reset_rate_limit_state()
    ip = "3.3.3.3"
    burst_limit = RATE_LIMIT_CONFIGS["forecast"]["burst_requests"]

    for _ in range(burst_limit):
        check_rate_limit(ip, "forecast")

    # inventory must still be allowed for the same IP
    allowed, _ = check_rate_limit(ip, "inventory")
    assert allowed is True
    print("PASS: test_rate_limit_different_endpoints_independent")


def test_rate_limit_headers_present():
    """get_rate_limit_headers must return the 3 required header keys."""
    _reset_rate_limit_state()
    headers = get_rate_limit_headers("5.5.5.5", "dashboard")
    assert "X-RateLimit-Limit" in headers
    assert "X-RateLimit-Remaining" in headers
    assert "X-RateLimit-Window" in headers
    print("PASS: test_rate_limit_headers_present")


# ─── IP EXTRACTION TESTS ──────────────────────────────────────────────────────

def test_extract_ip_from_x_forwarded_for():
    event = {"headers": {"X-Forwarded-For": "203.0.113.5, 70.41.3.18, 150.172.238.178"}}
    ip = extract_client_ip(event)
    assert ip == "203.0.113.5"
    print("PASS: test_extract_ip_from_x_forwarded_for")


def test_extract_ip_from_request_context_v1():
    event = {"requestContext": {"identity": {"sourceIp": "198.51.100.22"}}}
    ip = extract_client_ip(event)
    assert ip == "198.51.100.22"
    print("PASS: test_extract_ip_from_request_context_v1")


def test_extract_ip_from_request_context_v2():
    event = {"requestContext": {"http": {"sourceIp": "198.51.100.99"}}}
    ip = extract_client_ip(event)
    assert ip == "198.51.100.99"
    print("PASS: test_extract_ip_from_request_context_v2")


def test_extract_ip_fallback_unknown():
    """Empty event must return 'unknown', not raise an exception."""
    ip = extract_client_ip({})
    assert ip == "unknown"
    print("PASS: test_extract_ip_fallback_unknown")


# ─── RUNNER ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("--- RUNNING CHUNK 2 SECURITY TESTS ---")

    # Validator: Happy path
    test_valid_forecast_payload()
    test_valid_auto_po_payload()
    test_valid_promotions_payload_with_optional_fields()
    test_valid_promotions_payload_without_optional_fields()

    # Validator: Rejection
    test_reject_wrong_type_forecast_days()
    test_reject_boolean_as_integer()
    test_reject_forecast_days_over_maximum()
    test_reject_zero_cartons()
    test_reject_negative_discount()
    test_reject_invalid_store_id_format()
    test_reject_sql_injection_in_store_id()
    test_reject_invalid_sku_id_in_list()
    test_reject_unknown_festival_key()
    test_reject_unknown_language()
    test_reject_missing_required_field()
    test_reject_extra_unknown_field()
    test_reject_non_dict_body()
    test_validation_error_response_format()

    # Rate limiter
    test_rate_limit_allows_within_limit()
    test_rate_limit_blocks_after_burst()
    test_rate_limit_different_ips_independent()
    test_rate_limit_different_endpoints_independent()
    test_rate_limit_headers_present()

    # IP extraction
    test_extract_ip_from_x_forwarded_for()
    test_extract_ip_from_request_context_v1()
    test_extract_ip_from_request_context_v2()
    test_extract_ip_fallback_unknown()

    print("--- ALL CHUNK 2 SECURITY TESTS PASSED SUCCESSFULLY! ---")
