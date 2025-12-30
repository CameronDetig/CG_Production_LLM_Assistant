# Quick Test Guide - Frontend

## Test Locally (No Lambda Required!)

### One-Command Start

```bash
cd frontend
./run_local.sh
```

This automatically:
1. Creates `.env` with local settings
2. Installs dependencies
3. Starts mock backend (port 8000)
4. Starts Gradio app (port 7860)

Open **http://localhost:7860** and start chatting!

---

## Manual Testing

### Terminal 1: Mock Backend
```bash
cd frontend
pip install -r requirements.txt
python mock_backend.py
```

### Terminal 2: Gradio App
```bash
cd frontend
cp .env.example .env
# Edit .env: API_ENDPOINT=http://localhost:8000/chat
python app.py
```

---

## Test Queries

Try these in the chat:

1. "Show me all Blender files with Cycles renders"
2. "Find 4K resolution files"
3. "What files were modified this week?"
4. "Show me files with dark moody lighting"

The mock backend will return simulated responses with file metadata.

---

## Connect to Real Lambda

Once Lambda is deployed:

1. Edit `frontend/.env`:
   ```
   API_ENDPOINT=https://your-api-id.execute-api.us-east-1.amazonaws.com/prod/chat
   ```

2. Run Gradio:
   ```bash
   python app.py
   ```

---

## Deploy to Hugging Face Spaces

1. Create Space at https://huggingface.co/spaces
2. Upload: `app.py`, `requirements.txt`
3. Add secret: `API_ENDPOINT` = your Lambda URL
4. Done! Space auto-deploys

---

## Troubleshooting

**Port already in use?**
```bash
# Kill processes on ports
lsof -ti:8000 | xargs kill
lsof -ti:7860 | xargs kill
```

**Dependencies not installing?**
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Can't connect to backend?**
- Check `.env` has correct `API_ENDPOINT`
- Verify mock backend is running (Terminal 1)
- Try: `curl http://localhost:8000/health`
