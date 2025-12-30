# CG Production LLM Assistant - Frontend

Gradio-based chat interface for the CG Production LLM Assistant.

## 🚀 Quick Start

### Local Testing (Recommended)

```bash
cd frontend
python start_backend.py  # Terminal 1
python app.py            # Terminal 2
```

Open http://localhost:7860 in your browser!

See [LOCAL_TESTING.md](LOCAL_TESTING.md) for detailed instructions.

---

## 📋 Features

- 💬 **Chat Interface** - Clean Gradio UI for natural conversations
- 🌊 **Streaming Responses** - Real-time token streaming from Bedrock
- 🔍 **Semantic Search** - CLIP and text embeddings for intelligent file discovery
- 🗄️ **Real Database** - Queries actual PostgreSQL database with production data
- 🤖 **AWS Bedrock** - Powered by Llama 3.2 11B Instruct
- 🚀 **Easy AWS Transition** - Local backend wraps Lambda code for seamless deployment

---

## 📁 Files

| File | Purpose |
|------|---------|
| `app.py` | Gradio frontend application |
| `local_backend.py` | Flask server that wraps Lambda handler |
| `start_backend.py` | Startup script with environment setup |
| `requirements.txt` | Python dependencies |
| `.env.example` | Environment variables template |
| `QUICKSTART.md` | Quick reference guide |
| `LOCAL_TESTING.md` | Detailed testing instructions |

---

## 🔧 Configuration

Create `.env` file:

```env
# Backend API endpoint
API_ENDPOINT=http://localhost:8000/chat

# Database configuration
DB_HOST=localhost
DB_NAME=cg_metadata
DB_USER=cguser
DB_PASSWORD=cgpass

# AWS Bedrock
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=us.meta.llama3-2-11b-instruct-v1:0
```

---

## 🏗️ Architecture

### Local Development
```
Gradio UI → local_backend.py (Flask)
              ↓
         Lambda Handler (wrapped)
              ↓
         PostgreSQL + Bedrock
```

### AWS Deployment
```
Gradio UI → API Gateway → Lambda
                           ↓
                    PostgreSQL + Bedrock
```

**Key Design:** The local backend wraps the Lambda handler, ensuring **100% code compatibility** between local and AWS deployments.

---

## 🚢 Deploying to AWS

When ready to deploy:

1. **Deploy Lambda function** (use `backend/` code)
2. **Update `.env`:**
   ```env
   API_ENDPOINT=https://your-api-id.execute-api.us-east-1.amazonaws.com/prod/chat
   ```
3. **No code changes needed!**

The local backend uses the exact same Lambda code, so what works locally will work in AWS.

---

## 🎨 Deploying to Hugging Face Spaces

1. Create Space at https://huggingface.co/spaces
2. Upload: `app.py`, `requirements.txt`
3. Add secret: `API_ENDPOINT` = your Lambda URL
4. Done! Space auto-deploys

---

## 📚 Documentation

- [QUICKSTART.md](QUICKSTART.md) - Quick reference guide
- [LOCAL_TESTING.md](LOCAL_TESTING.md) - Detailed testing instructions
- [../backend/README.md](../backend/README.md) - Backend/Lambda documentation

---

## 💡 Example Queries

- "Find 4K resolution Blender files"
- "List all video files with their durations"
- "What files were modified this week?"
- "Show me files with dark moody lighting"
- "Where are the files for the autumn character located?"

---

## 🔍 Troubleshooting

See [LOCAL_TESTING.md](LOCAL_TESTING.md#troubleshooting) for common issues and solutions.
