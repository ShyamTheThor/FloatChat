#!/usr/bin/env bash
# scripts/run.sh
# Starts the FloatChat backend and frontend concurrently

# Get the absolute path to the project root
PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

echo "🌊 Starting FloatChat (Phase 2 & 3)..."

# 1. Start the FastAPI backend in the background
echo "-> Starting FastAPI Backend on port 8000..."
cd "$PROJECT_ROOT"
source .venv/bin/activate
python -m uvicorn backend.api:app --reload --port 8000 &
BACKEND_PID=$!

# 2. Wait a moment for backend to initialize vector DB
sleep 3

# 3. Start the Vite React frontend in the foreground
echo "-> Starting React Frontend..."
cd "$PROJECT_ROOT/frontend"
npm run dev

# 4. Cleanup background processes when user hits Ctrl+C
trap "kill $BACKEND_PID" EXIT
