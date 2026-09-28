"""
validator.py - Strict Request Schema Validation (Chunk 2)
Part of BiscuitAI

Mental Model:
Every endpoint in our API Gateway → Lambda pipeline receives untrusted JSON from the browser.
This module is the FIRST thing the Lambda handler calls before any business logic runs.

Design Rule (per user guidelines):
  "Validate every input against a strict schema (type, length, format)
   and REJECT anything that doesn't match — don't just sanitize/escape."

This means:
  - Wrong type?    → 400 immediately. We do NOT coerce "3" to 3.
  - Too long?      → 400 immediately. We do NOT truncate.
  - Wrong pattern? → 400 immediately. We do NOT strip characters.
  - Unknown field? → 400 immediately (strict allowlist, no extra keys allowed).

Call hierarchy:
  lambda_function.handler()
    └── validate_request(endpoint_key, payload)   ← this module
          └── _check_field(value, rule)
"""

import re
from typing import Any, Dict, List

# ─── VALIDATION RESULT ───────────────────────────────────────────────────────

class ValidationError(Exception):
    """Raised when a request fails schema validation."""
    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"Validation failed on field '{field}': {message}")


# ─── ALLOWED VALUE SETS ───────────────────────────────────────────────────────
# Strict allowlists — inputs MUST match exactly.

VALID_FESTIVAL_KEYS = frozenset({"DURGA_PUJA", "DIWALI", "REGULAR"})
VALID_LANGUAGES     = frozenset({"en", "bn", "hi"})
VALID_STORE_ID_RE   = re.compile(r"^STR-\d{3,6}$")         # e.g. STR-001 to STR-999999
VALID_SKU_ID_RE     = re.compile(r"^SKU-\d{3,6}$")          # e.g. SKU-001 to SKU-999999

# ─── ENDPOINT SCHEMAS ─────────────────────────────────────────────────────────
# Each schema is a dict: field_name → rule dict.
# Rules supported:
#   type         : Python type or tuple of types (required)
#   required     : bool (default True)
#   min_val      : numeric minimum (inclusive)
#   max_val      : numeric maximum (inclusive)
#   min_len      : string / list minimum length
#   max_len      : string / list maximum length
#   pattern      : compiled regex the value must fully match
#   allowlist    : frozenset of allowed exact values
#   item_type    : type each element of a list must be (for list fields)
#   item_pattern : regex each list element must fully match

SCHEMAS: Dict[str, Dict[str, Any]] = {

    # POST /api/forecast
    "forecast": {
        "store_id": {
            "type": str,
            "min_len": 5, "max_len": 12,
            "pattern": VALID_STORE_ID_RE
        },
        "sku_id": {
            "type": str,
            "min_len": 5, "max_len": 12,
            "pattern": VALID_SKU_ID_RE
        },
        "festival_key": {
            "type": str,
            "allowlist": VALID_FESTIVAL_KEYS
        },
        "forecast_days": {
            "type": int,
            "min_val": 1, "max_val": 90
        },
        "sales_history": {
            "type": list,
            "min_len": 3, "max_len": 90,
            "item_type": (int, float),
            "required": True
        }
    },

    # POST /api/auto-po
    "auto_po": {
        "store_id": {
            "type": str,
            "min_len": 5, "max_len": 12,
            "pattern": VALID_STORE_ID_RE
        },
        "festival_key": {
            "type": str,
            "allowlist": VALID_FESTIVAL_KEYS
        },
        "sku_ids": {
            "type": list,
            "min_len": 1, "max_len": 20,
            "item_type": str,
            "item_pattern": VALID_SKU_ID_RE
        }
    },

    # POST /api/promotions
    "promotions": {
        "sku_name": {
            "type": str,
            "min_len": 2, "max_len": 80
        },
        "recommended_cartons": {
            "type": int,
            "min_val": 1, "max_val": 500
        },
        "festival_key": {
            "type": str,
            "allowlist": VALID_FESTIVAL_KEYS
        },
        "language": {
            "type": str,
            "allowlist": VALID_LANGUAGES,
            "required": False  # Optional — omit for all 3 languages
        },
        "discount_pct": {
            "type": (int, float),
            "min_val": 0.0, "max_val": 25.0,
            "required": False
        },
        "cutoff_day": {
            "type": str,
            "min_len": 2, "max_len": 15,
            "required": False
        },
        "send_to_telegram": {
            "type": bool,
            "required": False
        }
    },

    # GET /api/inventory  (query-string params arrive as strings — special handling)
    "inventory_query": {
        "store_id": {
            "type": str,
            "min_len": 5, "max_len": 12,
            "pattern": VALID_STORE_ID_RE,
            "required": False
        }
    }
}


# ─── CORE VALIDATION ENGINE ───────────────────────────────────────────────────

def _check_field(field_name: str, value: Any, rule: Dict[str, Any]) -> None:
    """
    Validates a single field value against its rule dictionary.
    Raises ValidationError immediately on first violation (fail-fast).
    """
    expected_type = rule.get("type")

    # 1. Bool guard FIRST — Python's bool is a subclass of int, so isinstance(True, int)
    #    returns True. We must explicitly reject booleans for any field typed as int/float
    #    to prevent True=1 / False=0 slipping through as valid integers.
    if isinstance(value, bool) and expected_type is not bool:
        type_name = expected_type.__name__ if hasattr(expected_type, "__name__") else str(expected_type)
        raise ValidationError(
            field_name,
            f"Boolean values are not permitted; expected {type_name}"
        )

    # 2. Type check — no coercion, ever
    if not isinstance(value, expected_type):
        type_name = expected_type.__name__ if hasattr(expected_type, "__name__") else str(expected_type)
        raise ValidationError(
            field_name,
            f"Expected type {type_name}, got {type(value).__name__}"
        )

    # 3. Numeric range check (bool already rejected above, so this is safe)
    if isinstance(value, (int, float)):
        min_v = rule.get("min_val")
        max_v = rule.get("max_val")
        if min_v is not None and value < min_v:
            raise ValidationError(field_name, f"Value {value} is below minimum {min_v}")
        if max_v is not None and value > max_v:
            raise ValidationError(field_name, f"Value {value} exceeds maximum {max_v}")

    # 3. String length and regex pattern check
    if isinstance(value, str):
        min_l = rule.get("min_len")
        max_l = rule.get("max_len")
        if min_l is not None and len(value) < min_l:
            raise ValidationError(field_name, f"String too short (min {min_l} chars)")
        if max_l is not None and len(value) > max_l:
            raise ValidationError(field_name, f"String too long (max {max_l} chars)")

        pattern = rule.get("pattern")
        if pattern is not None and not pattern.fullmatch(value):
            raise ValidationError(field_name, f"Value '{value}' does not match required format")

        allowlist = rule.get("allowlist")
        if allowlist is not None and value not in allowlist:
            raise ValidationError(
                field_name,
                f"Value '{value}' not in allowed set: {sorted(allowlist)}"
            )

    # 4. List length, item type, and item pattern check
    if isinstance(value, list):
        min_l = rule.get("min_len")
        max_l = rule.get("max_len")
        if min_l is not None and len(value) < min_l:
            raise ValidationError(field_name, f"List too short (min {min_l} items)")
        if max_l is not None and len(value) > max_l:
            raise ValidationError(field_name, f"List too long (max {max_l} items)")

        item_type = rule.get("item_type")
        item_pattern = rule.get("item_pattern")
        for idx, item in enumerate(value):
            # Bool guard applies to list items too — True/False must not count as int
            if isinstance(item, bool) and item_type is not bool:
                raise ValidationError(
                    f"{field_name}[{idx}]",
                    "Boolean values are not permitted in this list"
                )
            if item_type is not None and not isinstance(item, item_type):
                raise ValidationError(
                    f"{field_name}[{idx}]",
                    f"Expected item type {item_type}, got {type(item).__name__}"
                )
            if item_pattern is not None and isinstance(item, str):
                if not item_pattern.fullmatch(item):
                    raise ValidationError(
                        f"{field_name}[{idx}]",
                        f"Item '{item}' does not match required format"
                    )


def validate_request(schema_key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validates an entire request payload against the named schema.

    Rules:
      - Unknown/extra fields in the payload are REJECTED (strict allowlist).
      - Required fields that are missing are REJECTED.
      - Optional fields that are present are still fully validated.

    Args:
        schema_key: Key into SCHEMAS dict (e.g. "forecast", "auto_po")
        payload:    The parsed JSON body dict from the incoming request

    Returns:
        The validated payload (unchanged) if all checks pass.

    Raises:
        ValidationError: On first violation found.
        KeyError:        If schema_key is not defined (programming error, not user error).
    """
    if not isinstance(payload, dict):
        raise ValidationError("body", "Request body must be a JSON object")

    schema = SCHEMAS[schema_key]
    allowed_fields = set(schema.keys())

    # Reject any extra/unknown fields — strict allowlist, no extras permitted
    extra_fields = set(payload.keys()) - allowed_fields
    if extra_fields:
        raise ValidationError(
            "body",
            f"Unknown field(s) not permitted: {sorted(extra_fields)}"
        )

    # Validate each defined field
    for field_name, rule in schema.items():
        is_required = rule.get("required", True)  # Default: required
        value = payload.get(field_name)

        if value is None:
            if is_required:
                raise ValidationError(field_name, "Required field is missing")
            else:
                continue  # Optional field absent — skip

        _check_field(field_name, value, rule)

    return payload  # All checks passed; return payload unchanged


def build_validation_error_response(error: ValidationError) -> Dict[str, Any]:
    """
    Builds a safe HTTP 400 response body for a ValidationError.
    NEVER includes stack trace, internal paths, or database details.
    """
    return {
        "status": 400,
        "error": "Validation failed",
        "field": error.field,
        "detail": error.message
    }
