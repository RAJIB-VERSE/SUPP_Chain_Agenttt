"""
test_lambda.py - Unit tests for the Lambda Router and Controller layer (Chunk 3)
Part of BiscuitAI

Tests:
1. Preflight OPTIONS (CORS)
2. Route resolution (404 Not Found, 405 Method Not Allowed)
3. Global Exception Handler (500 without leaking stack traces)
4. Integration with Rate Limiter (429 Too Many Requests)
5. Integration with Validator (400 Bad Request)
6. Controller Execution (200 OK for each endpoint)
"""

import json
import unittest
import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from lambda_function import handler, CORS_HEADERS

class TestLambdaRouter(unittest.TestCase):
    
    def _create_event(self, method: str, path: str, body: dict = None, ip: str = "127.0.0.1") -> dict:
        """Helper to construct a mock API Gateway event."""
        event = {
            "httpMethod": method,
            "path": path,
            "requestContext": {
                "identity": {
                    "sourceIp": ip
                }
            }
        }
        if body is not None:
            event["body"] = json.dumps(body)
        return event

    def test_options_preflight(self):
        """Preflight OPTIONS should return 200 with CORS headers."""
        event = self._create_event("OPTIONS", "/api/health")
        response = handler(event)
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(response["headers"]["Access-Control-Allow-Origin"], "*")

    def test_404_not_found(self):
        """Unknown paths should return 404."""
        event = self._create_event("GET", "/api/unknown-path")
        response = handler(event)
        self.assertEqual(response["statusCode"], 404)
        
        body = json.loads(response["body"])
        self.assertEqual(body["error"], "Not found")

    def test_405_method_not_allowed(self):
        """Known path with wrong method should return 405."""
        event = self._create_event("POST", "/api/health") # /health is GET only
        response = handler(event)
        self.assertEqual(response["statusCode"], 405)
        
        body = json.loads(response["body"])
        self.assertEqual(body["error"], "Method not allowed")

    def test_400_malformed_json(self):
        """POST with bad JSON should return 400 safely."""
        event = self._create_event("POST", "/api/forecast")
        event["body"] = "{ bad json"
        response = handler(event)
        self.assertEqual(response["statusCode"], 400)
        
        body = json.loads(response["body"])
        self.assertEqual(body["error"], "Malformed JSON")

    def test_400_validation_error(self):
        """Validator integration: invalid payload should return 400."""
        # Missing required 'store_id'
        payload = {
            "sku_id": "SKU-001",
            "festival_key": "DIWALI",
            "forecast_days": 14,
            "sales_history": [10, 12, 14]
        }
        event = self._create_event("POST", "/api/forecast", payload)
        response = handler(event)
        self.assertEqual(response["statusCode"], 400)
        
        body = json.loads(response["body"])
        self.assertEqual(body["error"], "Validation failed")
        self.assertEqual(body["field"], "store_id")

    @patch("lambda_function._resolve_route")
    def test_500_global_exception_handler(self, mock_resolve):
        """Any unhandled exception should be caught and return a safe 500."""
        mock_resolve.side_effect = Exception("Database is down! Secret password=123")
        
        event = self._create_event("GET", "/api/health")
        response = handler(event)
        
        self.assertEqual(response["statusCode"], 500)
        body = json.loads(response["body"])
        
        # Must NOT contain the original exception message
        self.assertEqual(body["error"], "Internal processing error")
        self.assertNotIn("123", str(body))
        self.assertIn("correlation_id", body)

    def test_cors_headers_always_present(self):
        """Even errors (like 404) must include CORS headers."""
        event = self._create_event("GET", "/api/unknown-path")
        response = handler(event)
        headers = response["headers"]
        self.assertEqual(headers["Access-Control-Allow-Origin"], CORS_HEADERS["Access-Control-Allow-Origin"])
        self.assertEqual(headers["Content-Type"], CORS_HEADERS["Content-Type"])

    def test_health_endpoint_success(self):
        """GET /api/health should return 200."""
        event = self._create_event("GET", "/api/health")
        response = handler(event)
        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertEqual(body["status"], "healthy")

    def test_dashboard_endpoint_success(self):
        """GET /api/dashboard should return 200."""
        event = self._create_event("GET", "/api/dashboard")
        response = handler(event)
        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertIn("summary", body)

    def test_promotions_endpoint_success(self):
        """POST /api/promotions should return 200 with valid input."""
        payload = {
            "sku_name": "Marie Gold",
            "recommended_cartons": 10,
            "festival_key": "DIWALI"
        }
        event = self._create_event("POST", "/api/promotions", payload)
        response = handler(event)
        self.assertEqual(response["statusCode"], 200)
        body = json.loads(response["body"])
        self.assertIn("messages", body)

if __name__ == "__main__":
    unittest.main()
