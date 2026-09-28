# Architectural Decisions & Rationale

## Chunk 1: Core Algorithm Engine
- **Decision:** Python `datetime` for date operations instead of `pandas` inside core lambda logic.
- **Rationale:** `pandas` is a massive dependency (adds ~30-40MB to lambda layers and significantly slows cold starts). Keeping the runtime dependencies to just `boto3` (built-in) ensures sub-second cold starts and zero extra costs.

## Chunk 2: Security & Validation Layer
- **Decision:** "Reject-over-Sanitize" (Strict Schema Validation).
- **Rationale:** Attempting to sanitize bad data (e.g. converting string "1" to integer 1, or ignoring unknown fields) opens up edge-case vulnerabilities and silent data corruption. Any deviation from the exact JSON schema results in an immediate HTTP 400.
- **Decision:** Dual-window Rate Limiter (Token Bucket).
- **Rationale:** A simple fixed window rate limiter allows bursts at the edge of the window. We implemented a token bucket to smooth out request spikes and prevent aggressive scraping. State is kept in-memory for the hackathon (accepting that it resets on container spin-down) to avoid the cost of ElastiCache/Redis.

## Chunk 3: API Gateway & Routing
- **Decision:** Monolithic Lambda Handler (`lambda_function.py`).
- **Rationale:** Managing 6 different AWS Lambdas via API Gateway requires 6 different sets of permissions, logs, and cold starts. A single monolithic handler mapping paths in memory is easier to deploy, cheaper, and faster for a hackathon MVP.
- **Decision:** Correlation IDs masking 500 errors.
- **Rationale:** Stack traces must never reach the client (prevents reconnaissance attacks). We catch all unhandled exceptions, log the full trace to CloudWatch with a UUID, and return a clean 500 error containing only that UUID.

## Chunk 4: Storage & ML Pipeline
- **Decision:** DynamoDB (Pay-Per-Request Mode) for live inventory.
- **Rationale:** Relational databases (RDS) have high fixed hourly costs and connection limits. DynamoDB in On-Demand mode costs exactly $0.00 when not receiving traffic, making it the perfect choice for a zero-budget serverless hackathon.
- **Decision:** Offline ML Training in Colab + S3 Batch Uploads.
- **Rationale:** Training ML models inside Lambda or SageMaker is expensive. By doing the heavy lifting in a free Google Colab notebook, generating a nightly batch CSV of predictions, and pushing it to an S3 bucket, our Lambda backend can simply pull the pre-computed S3 CSV into memory. This keeps our AWS bill at $0.00 while delivering advanced Random Forest forecasting.
- **Decision:** In-memory caching of S3 ML predictions in Lambda (`_ml_forecast_cache`).
- **Rationale:** Downloading the ML predictions CSV from S3 on every single request would add ~50-100ms latency. By caching it in a global variable, only the first request on a new Lambda container (cold start) fetches the CSV, and subsequent requests read from memory (sub-millisecond).
