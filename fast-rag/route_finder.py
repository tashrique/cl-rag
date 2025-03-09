#!/usr/bin/env python3
"""
Route Finder - Tests multiple routes to find a working endpoint
Usage: python route_finder.py [base_url]
"""

import requests
import json
import sys
import time

# Get base URL from command line or default to localhost
base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost"

# Sample query for testing
test_query = {
    "query": "What is Berkeley?",
    "top_k": 3,
    "include_sources": True,
    "include_metadata": True
}

def print_separator():
    print("\n" + "=" * 60 + "\n")

def test_path(path, method="GET", data=None):
    """Test a specific endpoint."""
    url = f"{base_url}{path}"
    print(f"Testing {method} {url}")
    try:
        if method.upper() == "GET":
            response = requests.get(url, timeout=5)
        else:
            response = requests.post(url, json=data, timeout=10)

        print(f"  Status: {response.status_code}")
        if response.status_code < 400:
            print("  SUCCESS! 🎉")
            try:
                response_data = response.json()
                print(f"  Response: {json.dumps(response_data)[:200]}...")
                return True
            except:
                print(f"  Response: {response.text[:200]}...")
                return True
        else:
            print(f"  Failed with: {response.text[:100]}")
            return False
    except Exception as e:
        print(f"  Error: {str(e)}")
        return False

print_separator()
print(f"🔍 Scanning {base_url} for working Deep Search RAG endpoints")
print_separator()

# Test health endpoints
print("Testing health endpoints:")
health_paths = ["/health", "/api/health", "/api/routes/health"]
for path in health_paths:
    test_path(path)

print_separator()
print("Testing root endpoints:")
root_paths = ["/", "/api", "/api/routes", "/api/routes/chat"]
for path in root_paths:
    test_path(path)

print_separator()
print("Testing deep search query endpoints with POST:")
query_paths = [
    # Direct endpoint variations
    "/query",
    "/deep-search/query",
    # API routes variations
    "/api/query",
    "/api/deep-search/query",
    "/api/routes/query",
    "/api/routes/deep-search/query",
    # Chat API variations
    "/api/chat/query",
    "/api/chat/deep-search/query",
    "/api/routes/chat/query",
    "/api/routes/chat/deep-search/query",
    # Other variations to try
    "/v1/query",
    "/api/v1/query",
    "/deep-search",
    "/rag/query",
    "/api/rag/query"
]

working_endpoints = []
for path in query_paths:
    success = test_path(path, "POST", test_query)
    if success:
        working_endpoints.append(path)
    time.sleep(0.5)  # Small delay to avoid overwhelming the server

print_separator()
if working_endpoints:
    print("✅ Working endpoints found!")
    for endpoint in working_endpoints:
        print(f"- POST {base_url}{endpoint}")
    
    # Print curl example for the first working endpoint
    print("\nExample CURL command:")
    print(f"curl -X POST {base_url}{working_endpoints[0]} \\")
    print("  -H \"Content-Type: application/json\" \\")
    print("  -d '{\"query\": \"What is Berkeley?\", \"top_k\": 3, \"include_sources\": true, \"include_metadata\": true}'")
else:
    print("❌ No working endpoints found. Suggestions:")
    print("1. Check your Docker port mapping (-p host:container)")
    print("2. Verify the app is running inside the container")
    print("3. Try accessing the Swagger docs at {base_url}/docs")
    print("4. Check the app logs for errors")

print_separator() 