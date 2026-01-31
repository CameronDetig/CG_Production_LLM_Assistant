#!/bin/bash
# Script to run the full stack locally for testing
# Starts the backend Flask server and the frontend Gradio app

set -e

# Get absolute paths
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend_gradio"

echo "=================================================="
echo "🚀 Starting Local Integration Test Stack"
echo "=================================================="
echo "📂 Project Root: $PROJECT_ROOT"
echo ""

# Check python virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  No virtual environment active."
    echo "   Activating default venv if it exists..."
    if [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
        source "$PROJECT_ROOT/.venv/bin/activate"
        echo "✅ Activated .venv"
    else
        echo "❌ Error: Please activate your virtual environment first."
        exit 1
    fi
fi

# Ensure Flask and Flask-CORS are installed
if ! python3 -c "import flask, flask_cors" 2>/dev/null; then
    echo "📦 Installing flask and flask-cors..."
    pip3 install flask flask-cors
fi

echo ""
echo "1️⃣  Starting Backend Server (localhost:5000)..."
# Start backend in background and save PID
cd "$BACKEND_DIR"
python3 testing/lambda_server.py &
BACKEND_PID=$!
echo "   PID: $BACKEND_PID"

# Function to kill backend on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down backend server (PID: $BACKEND_PID)..."
    kill $BACKEND_PID
    echo "✅ Done"
}
trap cleanup EXIT

# Wait for backend to start
echo "   Waiting for backend..."
sleep 2

echo ""
echo "2️⃣  Starting Frontend (Gradio)..."
echo "   Pointing to local API: http://localhost:5000/chat"
echo ""

# Clean up temp environment variable after running
cd "$FRONTEND_DIR"
export API_ENDPOINT="http://localhost:5000"
python3 app.py
