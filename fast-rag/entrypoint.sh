#!/bin/bash
set -e

# Check for required environment variables
if [ -z "$GEMINI_API_KEY" ]; then
  echo "ERROR: GEMINI_API_KEY environment variable is not set"
  exit 1
fi

if [ -z "$PINECONE_API_KEY" ]; then
  echo "ERROR: PINECONE_API_KEY environment variable is not set"
  exit 1
fi

echo "Starting Fast Search RAG API Server on port $PORT"
echo "Using Pinecone as vector database"

# Run the application using uvicorn
if [ "${ENVIRONMENT:-production}" = "development" ]; then
    # Development mode with auto-reload
    exec python -m uvicorn flare_ai_rag.main:create_app --host ${HOST:-0.0.0.0} --port ${PORT:-8002} --reload --factory
else
    # Production mode
    exec python -m uvicorn flare_ai_rag.main:create_app --host ${HOST:-0.0.0.0} --port ${PORT:-8002} --factory
fi
