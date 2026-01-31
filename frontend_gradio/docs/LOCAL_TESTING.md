# Local Testing Guide

### 1. Run the Frontend

```bash
cd frontend_gradio
python app.py
```

The app will start at **http://localhost:7860**.

### 2. Connect to Backend

The frontend needs to connect to the backend API. Ideally, you should connect to your deployed **AWS Lambda** backend.

**Option A: Connect to AWS Backend (Recommended)**
Ensure your `.env` file points to your Lambda URL:
```env
API_ENDPOINT=https://fhvltd2p33ejzyk5l5tgxyz4340qrghe.lambda-url.us-east-1.on.aws
```

**Option B: Connect to Local Backend (Advanced)**
If you are running the backend code locally (requires complex setup), point to localhost:
```env
API_ENDPOINT=http://localhost:8000/chat
```

Open **http://localhost:7860** in your browser.

---

## Test Queries

Try these in the chat:

1. "Find 4K resolution Blender files"
2. "List all video files with their durations"
3. "What files were modified this week?"
4. "Show me files with dark moody lighting"

The backend queries your **real PostgreSQL database** and uses **AWS Bedrock** for responses!

---

## Prerequisites

Before running locally:

- ✅ PostgreSQL running: `docker start cg_postgres`
- ✅ AWS credentials configured: `aws configure`
- ✅ `.env` file created with database credentials

---

## Connect to Deployed Lambda

Once Lambda is deployed:

1. Edit `frontend_gradio/.env`:
   ```env
   API_ENDPOINT=https://your-api-id.execute-api.us-east-1.amazonaws.com/prod/chat
   ```

2. Run Gradio:
   ```bash
   python app.py
   ```

---

## Troubleshooting

**Database Connection Failed?**
```bash
# Check if PostgreSQL is running
docker ps --filter "name=cg_postgres"

# Start if not running
docker start cg_postgres
```

**Bedrock Connection Failed?**
```bash
# Verify AWS credentials
aws sts get-caller-identity

# Check Bedrock access
aws bedrock list-foundation-models --region us-east-1
```

**Port already in use?**
```bash
# Windows
netstat -ano | findstr :8000
netstat -ano | findstr :7860

# Linux/Mac
lsof -ti:8000 | xargs kill
lsof -ti:7860 | xargs kill
```

**Can't connect to backend?**
- Check `.env` has correct `API_ENDPOINT=http://localhost:8000/chat`
- Verify local backend is running (Terminal 1)
- Try: `curl http://localhost:8000/health`
