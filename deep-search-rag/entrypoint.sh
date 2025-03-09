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

echo "Starting Deep Search RAG API Server on port $PORT"

# Start Qdrant in the background
echo "Starting Qdrant vector database..."
qdrant &

# Wait until Qdrant is ready
echo "Waiting for Qdrant to initialize..."
until curl -s http://127.0.0.1:6333/collections >/dev/null 2>&1; do
  echo "Qdrant is not ready yet, waiting..."
  sleep 5
done
echo "Qdrant is up and running!"

# Run the application using uvicorn
if [ "${ENVIRONMENT:-production}" = "development" ]; then
    # Development mode with auto-reload
    exec python -m uvicorn flare_ai_rag.main:create_app --host ${HOST:-0.0.0.0} --port ${PORT:-8001} --reload --factory
else
    # Production mode
    exec python -m uvicorn flare_ai_rag.main:create_app --host ${HOST:-0.0.0.0} --port ${PORT:-8001} --factory
fi
