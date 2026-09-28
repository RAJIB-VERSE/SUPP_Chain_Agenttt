# Execution Flow (Traceability)

This document traces exactly how a request travels through the system. 
**Rule #1 Adherence:** "Document how execution actually travels - between files, functions, and modules. What calls what, in what order, and exactly which parts of that path you're modifying right now."

## 1. Cloud to Code Entry
1. **API Gateway** receives the HTTP request.
2. It routes the request to **AWS Lambda**.
3. Lambda executes `lambda_function.py : handler(event, context)`.

## 2. Global Middleware Stack (Inside `lambda_function.py : handler()`)
1. **`extract_client_ip(event)`** -> Determines the caller's IP address (from API Gateway headers).
2. **`_resolve_route(raw_path, method)`** -> Looks up the path in the `ROUTES` dictionary to find the corresponding Controller and Validation Schema.
3. **`check_rate_limit(ip, endpoint_key)`** -> Checks if the IP has exceeded the token bucket limits (in `rate_limiter.py`).
4. **`_parse_body(event)`** or **`_parse_qs(event)`** -> Extracts the JSON body or query parameters safely, preventing JSON decode crashes.
5. **`validate_request(schema_key, payload)`** -> Sends the payload to `validator.py`. If it fails schema validation, raises `ValidationError` resulting in an immediate 400 Bad Request.

## 3. Controller Execution (Business Logic)
Once validated, the payload is passed to the specific controller in `lambda_function.py`.

### Example 1: `forecast_controller` (POST /api/forecast)
1. **Extracts** `store_id`, `sku_id`, `festival_key`, `forecast_days`, `sales_history`.
2. **Looks up** category internally using `_find_sku(sku_id)`.
3. **ML Integration (`db.get_ml_prediction`)**:
   - Calls `backend/db.py` to check if a highly accurate Random Forest prediction exists in the cached S3 CSV for this store/sku/festival.
   - If `db.py` cache is empty, it downloads and parses the CSV from S3 (`biscuitai-ml-predictions-*`).
4. **Core Algorithm (`forecasting.py : forecast_demand`)**:
   - Calculates the base statistical demand.
   - Applies the festive multiplier based on the SKU's category.
5. **Live DB Lookup (`db.get_inventory`)**:
   - Fetches the real-time `current_stock_units` from the live DynamoDB table (`BiscuitAI_Inventory`).
6. **Risk Assessment (`forecasting.py : assess_stockout_risk`)**:
   - Calculates days of inventory remaining, stockout risk level (CRITICAL, WARNING, HEALTHY), and projected revenue loss.
7. **Returns** JSON payload enriched with both the Machine Learning engine output and real-time statistical smoothing.

### Example 2: `inventory_controller` (GET /api/inventory)
1. **Live DB Query (`db.get_inventory`)**:
   - If `store_id` is provided, executes a DynamoDB `query` (O(1) partition access).
   - If no `store_id`, executes a DynamoDB `scan` (O(N) full table scan).
2. Loops through results, joining static `sku` and `store` metadata.
3. Calculates `assess_stockout_risk` dynamically for every row.
4. Returns list of inventory with computed risk levels.

## 4. Response & Error Egress
1. The controller returns a tuple: `(status_code, response_body)`.
2. **`_build_response()`** is called to serialize the body to JSON string and append standard `CORS_HEADERS`.
3. If an unhandled exception occurs anywhere in the stack, the `except Exception:` block catches it, logs the full `traceback.format_exc()` to CloudWatch with a generated `correlation_id`, and returns a generic 500 error containing only the `correlation_id` to the client.
