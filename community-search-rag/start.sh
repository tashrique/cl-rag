#!/bin/bash
set -e

echo "Starting Community Search RAG API Server on port $PORT"

# Run the application using uvicorn
if [ "${ENVIRONMENT:-production}" = "development" ]; then
    # Development mode with auto-reload
    exec python -m uvicorn flare_ai_rag.main:create_app --host ${HOST:-0.0.0.0} --port ${PORT:-8004} --reload --factory
else
    # Production mode
    exec python -m uvicorn flare_ai_rag.main:create_app --host ${HOST:-0.0.0.0} --port ${PORT:-8004} --factory
fi 