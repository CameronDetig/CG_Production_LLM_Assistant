#!/bin/bash

# Local testing script for frontend
# Starts both mock backend and Gradio app

set -e

echo "=========================================="
echo "🚀 Starting Local Frontend Testing"
echo "=========================================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from template..."
    cp .env.example .env
    echo "API_ENDPOINT=http://localhost:8000/chat" > .env
    echo "USE_STREAMING=true" >> .env
    echo "✅ Created .env with local settings"
    echo ""
fi

# Check if dependencies are installed
if ! python -c "import gradio" 2>/dev/null; then
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt
    echo "✅ Dependencies installed"
    echo ""
fi

echo "Starting services..."
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down services..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start mock backend in background
echo "1️⃣  Starting mock backend on http://localhost:8000..."
python mock_backend.py > backend.log 2>&1 &
BACKEND_PID=$!
sleep 2

# Check if backend started successfully
if ! curl -s http://localhost:8000/health > /dev/null; then
    echo "❌ Failed to start mock backend"
    cat backend.log
    exit 1
fi

echo "✅ Mock backend running (PID: $BACKEND_PID)"
echo ""

# Start Gradio app in background
echo "2️⃣  Starting Gradio app on http://localhost:7860..."
python app.py > frontend.log 2>&1 &
FRONTEND_PID=$!
sleep 3

echo "✅ Gradio app running (PID: $FRONTEND_PID)"
echo ""

echo "=========================================="
echo "✅ All services started!"
echo "=========================================="
echo ""
echo "📱 Open in browser: http://localhost:7860"
echo ""
echo "Logs:"
echo "  - Backend: tail -f backend.log"
echo "  - Frontend: tail -f frontend.log"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Wait for user interrupt
wait
