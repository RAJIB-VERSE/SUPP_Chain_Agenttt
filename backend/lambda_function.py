"""
lambda_function.py - Lambda Router, Controller & Error Handler (Chunk 3)
Part of BiscuitAI

Mental Model:
This is the SINGLE entry point for all API Gateway requests. It is the only file
AWS Lambda calls. Every request flows through this exact sequence — no exceptions:

  1. extract_client_ip()         — who is calling?
  2. _resolve_route()            — do we serve this path + method?
  3. check_rate_limit()          — is this IP within request budget?
  4. _parse_body() / _parse_qs() — safely decode the request payload
  5. validate_request()          — does the payload match our strict schema?
  6. controller()                — run business logic with clean, validated input
  7. _build_response()           — wrap result in consistent JSON + CORS headers

If ANYTHING outside step 6 fails, a safe generic error is returned to the client.
The full traceback is logged to CloudWatch with a correlation_id for debugging.
The correlation_id appears in BOTH the CloudWatch log and the client 500 response —
so errors are traceable without leaking internal paths, filenames, or stack frames.

Call hierarchy (read top-to-bottom, left-to-right):
  handler(event, context)
    ├── extract_client_ip(event)
    ├── _resolve_route(path, method)
    ├── check_rate_limit(ip, endpoint_key)
    ├── _parse_body(event) OR _parse_qs(event)
    ├── validate_request(schema_key, payload)
    └── controller(payload, event)
          ├── health_controller()
          ├── dashboard_controller()
          ├── inventory_controller()
          ├── forecast_controller()      → forecasting.py
          ├── auto_po_controller()       → auto_po.py
          └── promotions_controller()    → promotions.py
"""

import json
import logging
import traceback
import uuid

from validator import validate_request, build_validation_error_response, ValidationError
from rate_limiter import check_rate_limit, extract_client_ip, get_rate_limit_headers
from forecasting import forecast_demand, assess_stockout_risk, calculate_average_daily_demand
from auto_po import (
    calculate_demand_std_dev,
    calculate_safety_stock,
    calculate_reorder_point,
    calculate_recommended_order_quantity,
    generate_draft_purchase_order
)
from promotions import generate_promotional_message
from seed_data import STORES, SKUS
import db

# ─── LOGGING ─────────────────────────────────────────────────────────────────
# CloudWatch receives everything at INFO+ level by default in Lambda.
# NEVER log request bodies or user data at INFO — only at DEBUG (disabled in prod).

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ─── CORS HEADERS ─────────────────────────────────────────────────────────────
# Applied to EVERY response including errors, 404s, and 429s.
# This prevents browser CORS errors from masking the real HTTP status code.

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, X-Requested-With",
    "Content-Type": "application/json"
}


# ─── RESPONSE BUILDER ─────────────────────────────────────────────────────────

def _build_response(status_code: int, body: dict, extra_headers: dict = None) -> dict:
    """
    Builds the API Gateway Lambda proxy integration response format.
    Merges CORS headers + any endpoint-specific headers (e.g. X-RateLimit-*).
    Body is always serialised to a JSON string — never a raw dict.
    """
    headers = {**CORS_HEADERS}
    if extra_headers:
        headers.update(extra_headers)

    return {
        "statusCode": status_code,
        "headers": headers,
        "body": json.dumps(body, ensure_ascii=False, default=str)
    }


# ─── BODY PARSER ──────────────────────────────────────────────────────────────

def _parse_body(event: dict):
    """
    Safely parses the JSON request body from a Lambda event.
    Returns (parsed_dict, None) on success.
    Returns (None, error_response) if body is missing, empty, or malformed JSON.
    Never raises — all exceptions are caught and returned as a safe 400 response.
    """
    raw_body = event.get("body") or ""
    if not raw_body.strip():
        return None, _build_response(400, {
            "status": 400,
            "error": "Request body is required",
            "detail": "POST endpoints require a JSON body"
        })
    try:
        parsed = json.loads(raw_body)
        return parsed, None
    except (json.JSONDecodeError, ValueError):
        return None, _build_response(400, {
            "status": 400,
            "error": "Malformed JSON",
            "detail": "Request body must be valid JSON"
        })


def _parse_qs(event: dict) -> dict:
    """
    Safely extracts query string parameters from a Lambda event.
    Returns an empty dict if none are present — never raises.
    """
    return event.get("queryStringParameters") or {}


# ─── SKU LOOKUP HELPERS ───────────────────────────────────────────────────────

def _find_sku(sku_id: str) -> dict:
    """Returns the SKU dict for a given sku_id, or empty dict if not found."""
    for sku in SKUS:
        if sku["sku_id"] == sku_id:
            return sku
    return {}


def _find_inventory(store_id: str, sku_id: str) -> dict:
    """Returns the live inventory record for (store_id, sku_id) from DynamoDB, or empty dict."""
    records = db.get_inventory(store_id, sku_id)
    return records[0] if records else {}


def _find_store(store_id: str) -> dict:
    """Returns the store dict for a given store_id, or empty dict."""
    for store in STORES:
        if store["store_id"] == store_id:
            return store
    return {}


# ─── CONTROLLERS ─────────────────────────────────────────────────────────────
# Each controller receives:
#   payload : validated dict (body for POST, query params for GET)
#   event   : the raw Lambda event (for context — not for re-reading body)
# Each controller returns:
#   (status_code: int, response_body: dict)

def health_controller(payload: dict, event: dict):
    """GET /api/health — liveness check. No auth, no rate limit key, no body."""
    return 200, {
        "status": "healthy",
        "service": "BiscuitAI Supply Chain",
        "version": "1.0.0",
        "region": "ap-south-1",
        "chunks_deployed": ["chunk1-core-logic", "chunk2-security", "chunk3-lambda"]
    }


def dashboard_controller(payload: dict, event: dict):
    """
    GET /api/dashboard — aggregate summary across all stores and SKUs.
    Uses seed data (Chunk 4 will replace with DynamoDB queries).
    """
    all_inventory = db.get_inventory()
    total_stores = len(STORES)
    critical_count = 0
    warning_count = 0
    healthy_count = 0
    total_sku_records = len(all_inventory)

    for inv in all_inventory:
        sku = _find_sku(inv["sku_id"])
        store = _find_store(inv["store_id"])
        history = inv.get("sales_history_14d", [])
        if not history:
            continue

        avg_demand = calculate_average_daily_demand(history)
        risk = assess_stockout_risk(
            current_stock=inv["current_stock_units"],
            adjusted_daily_demand=avg_demand,
            lead_time_days=store.get("lead_time_days", 2),
            unit_price=sku.get("unit_price_inr", 30.0)
        )
        level = risk["risk_level"]
        if level == "CRITICAL":
            critical_count += 1
        elif level == "WARNING":
            warning_count += 1
        else:
            healthy_count += 1

    return 200, {
        "summary": {
            "total_stores": total_stores,
            "total_sku_records_monitored": total_sku_records,
            "critical_stockout_alerts": critical_count,
            "warning_alerts": warning_count,
            "healthy_sku_records": healthy_count
        },
        "data_source": "DynamoDB (Live)",
        "note": "Machine Learning Forecasts pulled from S3 (Chunk 4 Complete)"
    }


def inventory_controller(payload: dict, event: dict):
    """
    GET /api/inventory?store_id=STR-001 — per-store inventory status with risk assessment.
    Returns all stores if store_id is not provided.
    """
    store_id_filter = payload.get("store_id")  # already validated if present
    
    # Query DynamoDB efficiently if store_id is provided, else full scan
    live_inventory = db.get_inventory(store_id=store_id_filter)
    results = []

    for inv in live_inventory:
        if inv.get("store_id") == "CONFIG":
            continue

        sku = _find_sku(inv.get("sku_id", ""))
        store = _find_store(inv.get("store_id", ""))
        history = inv.get("sales_history_14d", [])
        avg_demand = calculate_average_daily_demand(history) if history else 0.0

        risk = assess_stockout_risk(
            current_stock=inv.get("current_stock_units", 0),
            adjusted_daily_demand=avg_demand,
            lead_time_days=store.get("lead_time_days", 2),
            unit_price=sku.get("unit_price_inr", 30.0)
        )

        results.append({
            "store_id": inv.get("store_id", "Unknown"),
            "store_name": store.get("name", "Unknown"),
            "sku_id": inv.get("sku_id", "Unknown"),
            "sku_name": sku.get("name", "Unknown"),
            "category": sku.get("category", "Unknown"),
            "current_stock_units": inv.get("current_stock_units", 0),
            "avg_daily_demand": avg_demand,
            "risk_level": risk["risk_level"],
            "days_of_inventory": risk["days_of_inventory"],
            "units_short": risk["units_short"],
            "projected_revenue_loss_inr": risk["projected_revenue_loss_inr"]
        })

    if store_id_filter and not results:
        return 404, {
            "status": 404,
            "error": "Store not found",
            "detail": f"No inventory records found for store_id '{store_id_filter}'"
        }

    return 200, {
        "store_id_filter": store_id_filter or "ALL",
        "record_count": len(results),
        "inventory": results
    }


def forecast_controller(payload: dict, event: dict):
    """
    POST /api/forecast — demand forecast with festive multiplier for a specific SKU.
    Looks up SKU category internally — not exposed to client.
    """
    store_id = payload["store_id"]
    sku_id = payload["sku_id"]
    festival_key = payload["festival_key"]
    forecast_days = payload["forecast_days"]
    sales_history = payload["sales_history"]

    # Internal category lookup — client only sends sku_id, not category
    # This prevents category injection while still applying correct multipliers
    sku = _find_sku(sku_id)
    category = sku.get("category", "General")

    forecast = forecast_demand(
        sales_history=sales_history,
        forecast_days=forecast_days,
        festival_key=festival_key,
        category=category
    )

    # 🚀 CHUNK 4 ML PIPELINE INTEGRATION
    # Pull the highly accurate Random Forest prediction from the AWS S3 batch upload
    ml_prediction = db.get_ml_prediction(store_id, sku_id, festival_key)
    if ml_prediction is not None:
        forecast["ml_model_prediction_cartons"] = ml_prediction
        forecast["engine_used"] = "RandomForest (Offline Batch) + Realtime Smoothing"
    else:
        forecast["engine_used"] = "Realtime Statistical Smoothing"

    # Enrich with stockout risk using live DynamoDB stock
    inv = _find_inventory(store_id, sku_id)
    store = _find_store(store_id)
    current_stock = inv.get("current_stock_units", 0)

    risk = assess_stockout_risk(
        current_stock=current_stock,
        adjusted_daily_demand=forecast["adjusted_daily_demand"],
        lead_time_days=store.get("lead_time_days", 2),
        unit_price=sku.get("unit_price_inr", 30.0)
    )

    return 200, {
        "store_id": store_id,
        "store_name": store.get("name", "Unknown"),
        "sku_id": sku_id,
        "sku_name": sku.get("name", "Unknown"),
        "category": category,
        "forecast": forecast,
        "stockout_risk": risk
    }


def auto_po_controller(payload: dict, event: dict):
    """
    POST /api/auto-po — generates a consolidated draft Purchase Order for all
    SKUs that need replenishment at the given store under the given festival demand.
    """
    store_id = payload["store_id"]
    festival_key = payload["festival_key"]
    sku_ids = payload["sku_ids"]

    store = _find_store(store_id)
    lead_time = store.get("lead_time_days", 2)

    sku_items = []
    for sku_id in sku_ids:
        sku = _find_sku(sku_id)
        if not sku:
            continue  # Unknown SKU — skip gracefully (already validated by pattern, but seed may not have it)

        inv = _find_inventory(store_id, sku_id)
        history = inv.get("sales_history_14d", [10, 12, 14, 16, 18])  # fallback baseline
        current_stock = inv.get("current_stock_units", 0)

        std_dev = calculate_demand_std_dev(history)
        safety_stock = calculate_safety_stock(std_dev, lead_time_days=lead_time)
        avg_demand = calculate_average_daily_demand(history)

        from forecasting import get_festive_multiplier
        multiplier = get_festive_multiplier(festival_key, sku.get("category", "General"))
        adjusted_demand = round(avg_demand * multiplier, 2)

        rop = calculate_reorder_point(adjusted_demand, lead_time, safety_stock)
        order = calculate_recommended_order_quantity(
            current_stock=current_stock,
            reorder_point=rop,
            adjusted_daily_demand=adjusted_demand,
            units_per_carton=sku.get("units_per_carton", 24)
        )

        if order["cartons_to_order"] > 0:
            sku_items.append({
                "sku_id": sku_id,
                "sku_name": sku.get("name", "Unknown"),
                "category": sku.get("category", "General"),
                "cartons_to_order": order["cartons_to_order"],
                "units_to_order": order["units_to_order"],
                "price_per_carton": sku.get("carton_price_inr", 720.0),
                "current_stock": current_stock,
                "reorder_point": rop,
                "adjusted_daily_demand": adjusted_demand
            })

    if not sku_items:
        return 200, {
            "store_id": store_id,
            "store_name": store.get("name", "Unknown"),
            "message": "All monitored SKUs are adequately stocked. No PO required.",
            "purchase_order": None
        }

    # Find distributor name from first store record (simplified — Chunk 4 will query DB)
    distributor_name = "Maa Tara FMCG Distributors"  # Seed default

    po = generate_draft_purchase_order(
        store_id=store_id,
        store_name=store.get("name", "Unknown"),
        distributor_name=distributor_name,
        sku_items=sku_items
    )

    return 200, {
        "store_id": store_id,
        "store_name": store.get("name", "Unknown"),
        "festival_key": festival_key,
        "purchase_order": po
    }


def promotions_controller(payload: dict, event: dict):
    """
    POST /api/promotions — generates WhatsApp/SMS broadcast messages in up to 3 languages.
    If 'language' is specified, returns only that language. Otherwise returns all three.
    """
    sku_name = payload["sku_name"]
    recommended_cartons = payload["recommended_cartons"]
    festival_key = payload["festival_key"]
    language = payload.get("language")           # Optional — en / bn / hi
    discount_pct = payload.get("discount_pct", 3.5)
    cutoff_day = payload.get("cutoff_day", "Wednesday")

    messages = generate_promotional_message(
        sku_name=sku_name,
        recommended_cartons=recommended_cartons,
        festival_key=festival_key,
        discount_pct=discount_pct,
        cutoff_day=cutoff_day
    )

    # If a specific language is requested, return only that message
    if language:
        lang_map = {"en": "english", "bn": "bengali", "hi": "hindi"}
        lang_key = lang_map.get(language)
        return 200, {
            "festival_key": festival_key,
            "sku_name": messages["sku_name"],
            "language": language,
            "message": messages.get(lang_key, "")
        }

    # Telegram integration (Hackathon Demo)
    send_to_telegram = payload.get("send_to_telegram", False)
    if send_to_telegram:
        import urllib.request
        import urllib.parse
        import json
        import ssl
        import os
        
        # Replace these with real credentials via BotFather
        TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
        TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")
        
        # Override with dynamic chat ID if someone messaged the bot
        try:
            response = db.dynamodb.Table(db.AWS_CONFIG["DYNAMODB_TABLE"]).get_item(
                Key={"store_id": "CONFIG", "sku_id": "TELEGRAM"}
            )
            if "Item" in response and "chat_id" in response["Item"]:
                TELEGRAM_CHAT_ID = response["Item"]["chat_id"]
        except Exception as e:
            logger.error(f"Could not fetch dynamic Telegram chat ID: {e}")
        
        text_to_send = f"🔔 *OmniStock AI Alert*\n\n{messages['english']}"
        
        if "YOUR_" not in TELEGRAM_BOT_TOKEN:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            data = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": text_to_send, "parse_mode": "Markdown"}).encode('utf-8')
            req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
            try:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                
                with urllib.request.urlopen(req, timeout=5, context=ctx) as response:
                    pass # Success!
            except Exception as e:
                logger.error(f"Telegram send failed: {e}")
                return 500, {"status": 500, "error": "Telegram notification failed"}

    return 200, {
        "festival_key": festival_key,
        "sku_name": messages["sku_name"],
        "cartons": messages["cartons"],
        "messages": {
            "english": messages["english"],
            "bengali": messages["bengali"],
            "hindi": messages["hindi"]
        }
    }


def telegram_webhook_controller(payload: dict, event: dict):
    """
    POST /api/telegram-webhook
    Telegram webhook endpoint. Receives updates from Telegram and stores the
    chat ID of whoever messages it into DynamoDB.
    """
    message = payload.get("message", {})
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    text = message.get("text", "")
    
    if chat_id:
        try:
            db.dynamodb.Table(db.AWS_CONFIG["DYNAMODB_TABLE"]).put_item(
                Item={
                    "store_id": "CONFIG",
                    "sku_id": "TELEGRAM",
                    "chat_id": str(chat_id),
                    "last_message": text
                }
            )
        except Exception as e:
            logger.error(f"Failed to save Telegram Chat ID: {e}")
            
    return 200, {"status": "ok"}


# ─── ROUTE TABLE ──────────────────────────────────────────────────────────────
# Maps: path → { method → (controller_fn, schema_key_or_None) }
#
# Design: Dict lookup is O(1) and eliminates if-elif chains.
# schema_key=None means: no body validation (GET endpoints or health).
# For GET endpoints, query string params are validated separately via
# the "inventory_query" schema when present.

ROUTES = {
    "/api/health": {
        "GET": (health_controller, None)
    },
    "/api/dashboard": {
        "GET": (dashboard_controller, None)
    },
    "/api/inventory": {
        "GET": (inventory_controller, "inventory_query")
    },
    "/api/forecast": {
        "POST": (forecast_controller, "forecast")
    },
    "/api/auto-po": {
        "POST": (auto_po_controller, "auto_po")
    },
    "/api/promotions": {
        "POST": (promotions_controller, "promotions")
    },
    "/api/telegram-webhook": {
        "POST": (telegram_webhook_controller, None)
    }
}


def _resolve_route(raw_path: str, method: str):
    """
    Normalises the path (strips trailing slash, strips API Gateway stage prefix)
    and resolves it against ROUTES.

    Returns:
        (controller_fn, schema_key, None)       — route found and method matches
        (None, None, 404_response)              — path not recognised
        (None, None, 405_response)              — path known, method not allowed
    """
    # Normalise: strip trailing slash
    path = raw_path.rstrip("/") or "/"

    # Strip API Gateway stage prefix if present (e.g. /prod/api/health → /api/health)
    if not path.startswith("/api") and "/api" in path:
        path = path[path.index("/api"):]

    route_methods = ROUTES.get(path)

    if route_methods is None:
        return None, None, _build_response(404, {
            "status": 404,
            "error": "Not found",
            "detail": f"No route registered for path '{path}'"
        })

    handler_tuple = route_methods.get(method.upper())
    if handler_tuple is None:
        allowed = ", ".join(route_methods.keys())
        return None, None, _build_response(405, {
            "status": 405,
            "error": "Method not allowed",
            "detail": f"'{method}' is not allowed on this endpoint. Allowed: {allowed}"
        })

    controller_fn, schema_key = handler_tuple
    return controller_fn, schema_key, None


# ─── MAIN LAMBDA HANDLER ──────────────────────────────────────────────────────

def handler(event: dict, context=None) -> dict:
    """
    AWS Lambda entry point. Orchestrates the full request lifecycle.
    Every possible failure path returns a safe JSON response — this function
    must NEVER raise an exception to the Lambda runtime.
    """
    correlation_id = uuid.uuid4().hex[:12]  # Short correlation ID for log-to-client tracing

    try:
        method = (event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method", "GET")).upper()
        raw_path = event.get("path") or event.get("rawPath") or "/"

        # ── Step 1: Handle OPTIONS preflight (CORS) ──────────────────────────
        if method == "OPTIONS":
            return _build_response(200, {"status": "ok"})

        # ── Step 2: Resolve route ─────────────────────────────────────────────
        controller_fn, schema_key, route_error = _resolve_route(raw_path, method)
        if route_error:
            return route_error

        # ── Step 3: Rate limiting ─────────────────────────────────────────────
        client_ip = extract_client_ip(event)
        endpoint_key = schema_key or "health"  # health endpoint uses its own config
        allowed, rate_info = check_rate_limit(client_ip, endpoint_key)
        if not allowed:
            return _build_response(429, rate_info, {
                "Retry-After": str(rate_info.get("retry_after", 30))
            })

        rate_headers = get_rate_limit_headers(client_ip, endpoint_key)

        # ── Step 4: Parse request payload ─────────────────────────────────────
        if method == "POST":
            payload, parse_error = _parse_body(event)
            if parse_error:
                return parse_error
        else:
            # GET: query string parameters
            payload = _parse_qs(event)

        # ── Step 5: Validate input ────────────────────────────────────────────
        if schema_key:
            try:
                validate_request(schema_key, payload)
            except ValidationError as ve:
                logger.warning(
                    "Validation failed | correlation_id=%s | path=%s | field=%s | detail=%s",
                    correlation_id, raw_path, ve.field, ve.message
                )
                return _build_response(400, build_validation_error_response(ve), rate_headers)

        # ── Step 6: Run controller ────────────────────────────────────────────
        status_code, response_body = controller_fn(payload, event)

        # Add correlation_id to all successful responses for hackathon demo traceability
        response_body["correlation_id"] = correlation_id
        return _build_response(status_code, response_body, rate_headers)

    except Exception:
        # ── Step 7: Global catch-all — log full traceback to CloudWatch,
        #    return a safe generic error to the client (no leak).
        logger.error(
            "Unhandled exception | correlation_id=%s\n%s",
            correlation_id, traceback.format_exc()
        )
        return _build_response(500, {
            "status": 500,
            "error": "Internal processing error",
            "correlation_id": correlation_id,
            "detail": "Please quote the correlation_id when reporting this issue"
        })
