"""
rate_limiter.py - Sliding Window Rate Limiter (Chunk 2)
Part of BiscuitAI

Mental Model:
Protects each API endpoint from abuse by tracking how many requests
a given client IP has made within a sliding time window.
When the limit is exceeded, the Lambda handler returns HTTP 429 immediately —
before any business logic, database access, or computation happens.

Design Decisions (per user guideline):
  "Add rate limiting appropriate to each endpoint type:
   stricter limits on authentication routes, moderate on public endpoints.
   Make all thresholds configurable, not hardcoded."

Implementation:
  - Sliding window counter stored in an in-memory dict per Lambda execution context.
  - On AWS Lambda, each concurrent container has its own memory, so this is a
    per-instance limiter. Sufficient for hackathon demo scale. For production,
    replace backing store with ElastiCache Redis or DynamoDB atomic counters.
  - All threshold constants are defined in one place (RATE_LIMIT_CONFIGS) —
    zero magic numbers scattered across code.

Call hierarchy:
  lambda_function.handler()
    └── check_rate_limit(client_ip, endpoint_key)  ← this module
          └── _get_window_count(ip, window_seconds)
"""

import time
from typing import Dict, Any, Tuple
from collections import defaultdict, deque


# ─── CONFIGURABLE RATE LIMIT THRESHOLDS ──────────────────────────────────────
# ALL limits live here. Change a number in ONE place, not scattered through code.
#
# Structure:
#   endpoint_key → {
#       "requests"       : max requests allowed in window
#       "window_seconds" : rolling window duration
#       "burst_requests" : short-burst allowance (smaller window = 5s)
#       "retry_after"    : seconds to tell client to wait (Retry-After header value)
#   }

RATE_LIMIT_CONFIGS: Dict[str, Dict[str, int]] = {
    # Read-only lightweight endpoints — most permissive
    "health": {
        "requests": 120,
        "window_seconds": 60,
        "burst_requests": 20,
        "retry_after": 10
    },
    "dashboard": {
        "requests": 60,
        "window_seconds": 60,
        "burst_requests": 10,
        "retry_after": 15
    },
    "inventory": {
        "requests": 60,
        "window_seconds": 60,
        "burst_requests": 10,
        "retry_after": 15
    },
    # Compute-heavy POST endpoints — moderate limits
    "forecast": {
        "requests": 30,
        "window_seconds": 60,
        "burst_requests": 5,
        "retry_after": 30
    },
    "auto_po": {
        "requests": 20,
        "window_seconds": 60,
        "burst_requests": 3,
        "retry_after": 30
    },
    "promotions": {
        "requests": 30,
        "window_seconds": 60,
        "burst_requests": 5,
        "retry_after": 30
    },
    # Default fallback for any unlisted endpoint — conservative
    "_default": {
        "requests": 20,
        "window_seconds": 60,
        "burst_requests": 5,
        "retry_after": 30
    }
}

# Burst window is always 5 seconds (short-spike protection)
BURST_WINDOW_SECONDS = 5


# ─── IN-MEMORY SLIDING WINDOW STORE ──────────────────────────────────────────
# Maps:  (client_ip, endpoint_key, window_type) → deque of UTC timestamps
# Deque allows O(1) append and O(1) popleft for the sliding window algorithm.
#
# KNOWN LIMITATION (documented, not hidden):
#   _request_log grows unboundedly for IPs that send requests and then stop.
#   Old deque entries are pruned per-key only when that same IP makes a new
#   request. For the hackathon single-Lambda demo, this is acceptable.
#   Production fix: replace with DynamoDB atomic counters with TTL, or
#   ElastiCache Redis with EXPIRE, which auto-clean idle IP entries.

_request_log: Dict[Tuple[str, str, str], deque] = defaultdict(deque)


# ─── CORE RATE LIMIT ENGINE ───────────────────────────────────────────────────

def _get_window_count(client_ip: str, endpoint_key: str, window_key: str, window_seconds: int) -> int:
    """
    Returns the number of requests made by client_ip on endpoint_key within
    the last `window_seconds` seconds, using a sliding window algorithm.
    Expired timestamps are evicted from the deque on each call.
    """
    store_key = (client_ip, endpoint_key, window_key)
    now = time.monotonic()
    cutoff = now - window_seconds

    log = _request_log[store_key]

    # Evict timestamps older than the window (sliding window pruning)
    while log and log[0] < cutoff:
        log.popleft()

    return len(log)


def _record_request(client_ip: str, endpoint_key: str, window_key: str) -> None:
    """Records the current timestamp for a request."""
    store_key = (client_ip, endpoint_key, window_key)
    _request_log[store_key].append(time.monotonic())


def check_rate_limit(client_ip: str, endpoint_key: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Checks whether a request from client_ip to endpoint_key is within rate limits.
    Records the request if allowed.

    Args:
        client_ip:    Extracted from the Lambda event sourceIp / X-Forwarded-For
        endpoint_key: One of the keys in RATE_LIMIT_CONFIGS (e.g. "forecast")

    Returns:
        (allowed: bool, info: dict)
        If allowed=True  → proceed with request
        If allowed=False → return HTTP 429 to client using info dict
    """
    config = RATE_LIMIT_CONFIGS.get(endpoint_key, RATE_LIMIT_CONFIGS["_default"])

    burst_count   = _get_window_count(client_ip, endpoint_key, "burst", BURST_WINDOW_SECONDS)
    rolling_count = _get_window_count(client_ip, endpoint_key, "rolling", config["window_seconds"])

    # Check burst limit first (stricter, shorter window)
    if burst_count >= config["burst_requests"]:
        return False, {
            "status": 429,
            "error": "Too many requests",
            "detail": f"Burst limit of {config['burst_requests']} requests per {BURST_WINDOW_SECONDS}s exceeded",
            "retry_after": config["retry_after"]
        }

    # Check rolling window limit
    if rolling_count >= config["requests"]:
        return False, {
            "status": 429,
            "error": "Too many requests",
            "detail": f"Rate limit of {config['requests']} requests per {config['window_seconds']}s exceeded",
            "retry_after": config["retry_after"]
        }

    # Within limits — record this request and allow
    _record_request(client_ip, endpoint_key, "burst")
    _record_request(client_ip, endpoint_key, "rolling")

    return True, {}


def get_rate_limit_headers(client_ip: str, endpoint_key: str) -> Dict[str, str]:
    """
    Builds informational rate-limit headers to include in successful responses.
    Allows clients to self-throttle before hitting the limit.
    """
    config = RATE_LIMIT_CONFIGS.get(endpoint_key, RATE_LIMIT_CONFIGS["_default"])
    rolling_count = _get_window_count(client_ip, endpoint_key, "rolling", config["window_seconds"])
    remaining = max(0, config["requests"] - rolling_count)

    return {
        "X-RateLimit-Limit": str(config["requests"]),
        "X-RateLimit-Remaining": str(remaining),
        "X-RateLimit-Window": str(config["window_seconds"])
    }


def extract_client_ip(lambda_event: Dict[str, Any]) -> str:
    """
    Safely extracts the client IP address from a Lambda API Gateway event.
    Falls back to 'unknown' if IP cannot be determined — never crashes.

    Checks in order:
      1. X-Forwarded-For header (set by API Gateway for real client IP)
      2. requestContext.identity.sourceIp (API Gateway v1 format)
      3. requestContext.http.sourceIp (API Gateway v2 HTTP API format)
    """
    # X-Forwarded-For: real_ip, proxy_ip, proxy_ip  → take the first (leftmost = real client)
    headers = lambda_event.get("headers") or {}
    xff = headers.get("X-Forwarded-For") or headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()

    # API Gateway v1 REST API
    request_context = lambda_event.get("requestContext", {})
    identity = request_context.get("identity", {})
    source_ip = identity.get("sourceIp", "")
    if source_ip:
        return source_ip

    # API Gateway v2 HTTP API
    http_ctx = request_context.get("http", {})
    source_ip_v2 = http_ctx.get("sourceIp", "")
    if source_ip_v2:
        return source_ip_v2

    return "unknown"
