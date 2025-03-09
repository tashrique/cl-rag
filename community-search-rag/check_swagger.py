#!/usr/bin/env python3
"""
Swagger Documentation Checker
Tries to locate and extract information from FastAPI's Swagger documentation
Usage: python check_swagger.py [base_url]
"""

import requests
import json
import sys
from urllib.parse import urljoin

base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8004"

def check_url(url, description):
    """Check a URL and report results."""
    print(f"Checking {description} at {url}...")
    try:
        response = requests.get(url, timeout=5)
        if response.status_code < 400:
            print(f"✅ Success! Status: {response.status_code}")
            try:
                data = response.json()
                return data
            except:
                print("⚠️ Response is not JSON")
                print(f"Content: {response.text[:200]}...")
        else:
            print(f"❌ Failed with status {response.status_code}")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    return None

def print_separator():
    print("\n" + "=" * 60 + "\n")

print_separator()
print(f"🔍 Checking FastAPI Swagger documentation for {base_url}")
print_separator()

# Check common FastAPI documentation URLs
paths = [
    "/docs",
    "/openapi.json",
    "/api/docs",
    "/api/openapi.json",
    "/swagger",
    "/swagger-ui",
    "/swagger/index.html",
    "/api/swagger",
    "/api/v1/docs",
    "/api/v1/openapi.json",
]

found_docs = False
openapi_data = None

# Check all common paths
for path in paths:
    url = urljoin(base_url + "/", path.lstrip("/"))
    data = check_url(url, f"FastAPI {path}")
    if data and path.endswith("openapi.json"):
        openapi_data = data
        found_docs = True
        print("Found OpenAPI schema!")
        break
    elif data or (path.endswith("docs") and data is not None):
        found_docs = True
        print(f"Found documentation at {url}")
        # If we find the docs UI, try to get the schema
        schema_url = urljoin(base_url + "/", "openapi.json")
        openapi_data = check_url(schema_url, "OpenAPI schema")
        break

# If we found an OpenAPI schema, extract the endpoints
if openapi_data:
    print_separator()
    print("📋 API Endpoints Detected:")
    
    if "paths" in openapi_data:
        for path, methods in openapi_data["paths"].items():
            for method, details in methods.items():
                method_upper = method.upper()
                summary = details.get("summary", "No summary")
                print(f"- {method_upper} {path}")
                print(f"  Summary: {summary}")
                if "requestBody" in details:
                    print("  Requires request body: Yes")
                print()
                
                # Provide an example if it's a POST endpoint
                if method_upper == "POST" and path.endswith("/query"):
                    print("Example CURL command:")
                    print(f"curl -X POST {base_url}{path} \\")
                    print("  -H \"Content-Type: application/json\" \\")
                    print("  -d '{\"query\": \"What is Berkeley?\", \"top_k\": 3, \"include_sources\": true, \"include_metadata\": true}'")
                    print()
    else:
        print("❌ No paths found in OpenAPI schema")

if not found_docs:
    print_separator()
    print("❌ No FastAPI Swagger documentation found.")
    print("Suggestions:")
    print("1. Make sure FastAPI is configured with docs_url='/docs'")
    print("2. Check that the server is running correctly")
    print("3. Try enabling documentation explicitly in your FastAPI app:")
    print("   app = FastAPI(docs_url='/docs', redoc_url='/redoc')")
    print("4. Check if the docs are disabled or under a different path")
    print("5. Try running the route_finder.py script to find working endpoints")

print_separator() 