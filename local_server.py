from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import urllib.parse
import sys
import os

# Ensure backend directory is in path so absolute imports in lambda_function work
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

try:
    from backend.lambda_function import handler
except ImportError as e:
    print(f"Failed to import lambda_function: {e}")
    sys.exit(1)

class LambdaWrapperHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self._route_request("OPTIONS")
        
    def do_GET(self):
        self._route_request("GET")
        
    def do_POST(self):
        self._route_request("POST")
        
    def _route_request(self, method):
        parsed_path = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed_path.query)
        # Flatten qs arrays
        qs_flat = {k: v[0] for k, v in qs.items()}
        
        body = ""
        if method == "POST":
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length > 0:
                body = self.rfile.read(content_length).decode('utf-8')
                
        # Construct the Lambda Event API Gateway would send
        event = {
            "httpMethod": method,
            "path": parsed_path.path,
            "queryStringParameters": qs_flat,
            "body": body,
            "requestContext": {
                "identity": {
                    "sourceIp": self.client_address[0]
                }
            }
        }
        
        # Call the actual Lambda monolithic handler
        response = handler(event, None)
        
        # Send back HTTP response
        self.send_response(response["statusCode"])
        for header, value in response.get("headers", {}).items():
            self.send_header(header, str(value))
        self.end_headers()
        
        self.wfile.write(response.get("body", "").encode('utf-8'))

if __name__ == "__main__":
    port = 8000
    server = HTTPServer(('127.0.0.1', port), LambdaWrapperHandler)
    print(f"Backend Server running at http://127.0.0.1:{port}/")
    print("Press Ctrl+C to stop.")
    server.serve_forever()
