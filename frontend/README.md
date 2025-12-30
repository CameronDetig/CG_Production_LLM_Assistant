# CG Production LLM Assistant - Frontend

Gradio-based chat interface for interacting with the CG Production LLM Assistant backend.

## Features

- 💬 **Chat Interface** - Clean, modern chat UI powered by Gradio
- 🌊 **Streaming Responses** - Real-time token streaming from Lambda backend
- 🧪 **Local Testing** - Mock backend for development without deploying Lambda
- 🎨 **Example Queries** - Pre-built examples to get started quickly
- 🚀 **Easy Deployment** - Ready for Hugging Face Spaces

---

## Quick Start

### Option 1: Local Testing (Mock Backend)

Test the frontend without deploying the Lambda backend:

```bash
# 1. Install dependencies
cd frontend
pip install -r requirements.txt

# 2. Set up environment
cp .env.example .env
# Edit .env and set: API_ENDPOINT=http://localhost:8000/chat

# 3. Start mock backend (Terminal 1)
python mock_backend.py

# 4. Start Gradio app (Terminal 2)
python app.py
```

Open http://localhost:7860 in your browser!

---

### Option 2: Connect to Deployed Lambda

Use the real Lambda backend:

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env and set your Lambda API endpoint:
# API_ENDPOINT=https://your-api-id.execute-api.us-east-1.amazonaws.com/prod/chat

# 3. Run Gradio app
python app.py
```

---

## Files

| File | Purpose |
|------|---------|
| `app.py` | Main Gradio application |
| `mock_backend.py` | Local mock server for testing |
| `requirements.txt` | Python dependencies |
| `.env.example` | Environment variables template |

---

## Environment Variables

Create a `.env` file with:

```bash
# Lambda API endpoint
API_ENDPOINT=https://your-api-id.execute-api.us-east-1.amazonaws.com/prod/chat

# Enable streaming (true/false)
USE_STREAMING=true
```

---

## Local Testing Workflow

### Terminal 1: Mock Backend
```bash
python mock_backend.py
```

Output:
```
============================================================
🚀 Mock Backend Server Starting
============================================================

This simulates the Lambda backend for local testing.
The Gradio frontend will connect to: http://localhost:8000/chat

To use this:
1. Set API_ENDPOINT=http://localhost:8000/chat in .env
2. Run this server: python mock_backend.py
3. Run Gradio app: python app.py

============================================================

 * Running on http://0.0.0.0:8000
```

### Terminal 2: Gradio App
```bash
python app.py
```

Output:
```
Running on local URL:  http://127.0.0.1:7860

To create a public link, set `share=True` in `launch()`.
```

---

## Example Queries

Try these queries in the chat interface:

- "Show me all Blender files with Cycles renders"
- "Find 4K resolution files"
- "What files were modified this week?"
- "Show me files with dark moody lighting"
- "List all video files with their durations"

---

## Deployment to Hugging Face Spaces

### 1. Create Space

1. Go to https://huggingface.co/spaces
2. Click "Create new Space"
3. Choose "Gradio" as SDK
4. Name it (e.g., `cg-production-assistant`)

### 2. Add Files

Upload these files to your Space:
- `app.py`
- `requirements.txt`
- `README.md` (optional)

### 3. Configure Secrets

In Space settings, add secret:
- **Name**: `API_ENDPOINT`
- **Value**: Your Lambda API URL

### 4. Deploy

Space will automatically build and deploy!

---

## Customization

### Change Theme

Edit `app.py`:
```python
theme=gr.themes.Soft(primary_hue="blue")  # Try: green, orange, purple
```

### Add Custom CSS

Modify the `custom_css` variable in `app.py`:
```python
custom_css = """
.gradio-container {
    max-width: 1200px !important;
}
"""
```

### Disable Streaming

Set in `.env`:
```bash
USE_STREAMING=false
```

---

## Troubleshooting

### "Could not connect to backend"

**Problem**: Gradio can't reach the API endpoint

**Solutions**:
1. Check `API_ENDPOINT` in `.env` is correct
2. Verify Lambda API is deployed and accessible
3. For local testing, ensure mock backend is running
4. Check CORS settings in Lambda

### "Request timed out"

**Problem**: Lambda is taking too long (cold start or slow query)

**Solutions**:
1. First request after deployment takes 10-15s (model loading)
2. Increase timeout in `app.py`: `timeout=120`
3. Check Lambda memory settings (should be 2048 MB)

### Streaming not working

**Problem**: Response appears all at once instead of streaming

**Solutions**:
1. Verify `USE_STREAMING=true` in `.env`
2. Check Lambda is returning SSE format
3. Test with mock backend first to isolate issue

---

## Development

### Running with Auto-Reload

```bash
# Gradio auto-reloads on file changes
python app.py
```

### Testing SSE Parsing

```bash
# Test mock backend directly
curl http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}'
```

---

## Next Steps

1. ✅ Test locally with mock backend
2. ⏳ Deploy Lambda backend
3. ⏳ Update `.env` with real API endpoint
4. ⏳ Deploy to Hugging Face Spaces
5. ⏳ Create Blender plugin

---

## Support

- **Mock Backend**: Simulates Lambda responses for local dev
- **Streaming**: Parses SSE events from Lambda
- **Error Handling**: Graceful fallbacks for connection issues
