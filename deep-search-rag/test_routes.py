#!/usr/bin/env python3
"""
Test script for Deep Search RAG API endpoints.
Usage: python test_routes.py [base_url]
Default base_url: http://localhost:8001
"""

import requests
import json
import sys
from typing import Dict, Any, Optional, Union

# Get base URL from command line or default to localhost:8001
base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8001"

def test_endpoint(url: str, method: str = "GET", data: Optional[Dict[str, Any]] = None) -> None:
    """Test an endpoint and print the result."""
    print(f"\nTesting {method} {url}")
    try:
        if method.upper() == "GET":
            response = requests.get(url, timeout=10)
        elif method.upper() == "POST":
            response = requests.post(url, json=data, timeout=10)
        else:
            print(f"Unsupported method: {method}")
            return
        
        print(f"Status code: {response.status_code}")
        if response.status_code == 200:
            print("Success!")
            try:
                print(json.dumps(response.json(), indent=2))
            except:
                print(response.text[:500] + "..." if len(response.text) > 500 else response.text)
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Request failed: {str(e)}")

# Test health endpoint
test_endpoint(f"{base_url}/health")

# Test root endpoint
test_endpoint(f"{base_url}/")

# Test query endpoint - direct access (might not be available in your config)
test_query = {
    "query": "Tell me about Berkeley",
    "top_k": 3,
    "include_sources": True,
    "include_metadata": True
}
test_endpoint(f"{base_url}/api/routes/chat/deep-search/query", "POST", test_query)

# Print all possible paths to try
print("\nOther paths that might work:")
print(f"- {base_url}/query")
print(f"- {base_url}/api/routes/chat/query")
print(f"- {base_url}/deep-search/query")
print(f"- {base_url}/api/routes/deep-search/query")

print("\nUse curl for manual testing:")
print(f"curl -X POST {base_url}/api/routes/chat/deep-search/query \\")
print("  -H \"Content-Type: application/json\" \\")
print("  -d '{\"query\": \"Tell me about Berkeley\", \"top_k\": 3, \"include_sources\": true, \"include_metadata\": true}'")

if __name__ == "__main__":
    print("Tests completed.") 