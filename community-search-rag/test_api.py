#!/usr/bin/env python3
import requests
import json
import sys

# Get base URL from command line or default to localhost:8004
base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8004"

# Test data
test_query = {
    "query": "Tell me about Berkeley",
    "top_k": 3,
    "include_sources": True,
    "include_metadata": True
}

# Test direct endpoint
direct_url = f"{base_url}/query"
print(f"Testing direct endpoint: {direct_url}")
try:
    response = requests.post(direct_url, json=test_query)
    print(f"Status code: {response.status_code}")
    if response.status_code == 200:
        print("Success!")
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"Request failed: {str(e)}")

print("\n" + "-"*50 + "\n")

# Test prefixed endpoint
prefixed_url = f"{base_url}/api/routes/chat/community-search/query"
print(f"Testing prefixed endpoint: {prefixed_url}")
try:
    response = requests.post(prefixed_url, json=test_query)
    print(f"Status code: {response.status_code}")
    if response.status_code == 200:
        print("Success!")
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"Request failed: {str(e)}")

# Test health endpoint
health_url = f"{base_url}/health"
print(f"\nTesting health endpoint: {health_url}")
try:
    response = requests.get(health_url)
    print(f"Status code: {response.status_code}")
    if response.status_code == 200:
        print("Success!")
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"Request failed: {str(e)}") 