#!/bin/bash
# Dfacto Backend Startup Script
# Run from anywhere: bash /Users/arnabb1998/Documents/Projects/Dfacto/dfacto_backend/start.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 Starting Dfacto backend..."
source .venv/bin/activate
LANGCHAIN_TRACING_V2=false uvicorn main:app --host 0.0.0.0 --port 8000
