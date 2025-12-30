# Quick Start Guide - Local Backend

## Prerequisites

✅ PostgreSQL running (Docker container `cg_postgres`)  
✅ AWS credentials configured (`aws configure`)  
✅ Python virtual environment activated  

## Start the Backend

```bash
cd frontend
python start_backend.py
```

You should see:
```
✅ Database connected: PostgreSQL 16.11 ...
✅ Bedrock connected: us.meta.llama3-2-11b-instruct-v1:0
✅ Semantic search working: 5 results

Starting Flask server...
API endpoint: http://localhost:8000/chat
```

## Start the Frontend

In a **new terminal**:

```bash
cd frontend
python app.py
```

Open http://localhost:7860 in your browser.

## Test Queries

Try these example queries:
- "Show me all Blender files with Cycles renders"
- "Find 4K resolution files"
- "What files were modified this week?"
- "Show me files with dark moody lighting"

## Troubleshooting

### Database Connection Failed

```bash
# Check if PostgreSQL is running
docker ps --filter "name=cg_postgres"

# Start if not running
docker start cg_postgres
```

### Bedrock Connection Failed

```bash
# Verify AWS credentials
aws sts get-caller-identity

# Check Bedrock access
aws bedrock list-foundation-models --region us-east-1
```

### Missing Environment Variables

Check `frontend/.env` file has:
```env
DB_HOST=localhost
DB_NAME=cg_metadata
DB_USER=cguser
DB_PASSWORD=cgpass
BEDROCK_MODEL_ID=us.meta.llama3-2-11b-instruct-v1:0
```

## Deploying to AWS

When ready to deploy:

1. Deploy Lambda function (use `backend/` code)
2. Update `frontend/.env`:
   ```env
   API_ENDPOINT=https://your-api-id.execute-api.us-east-1.amazonaws.com/prod/chat
   ```
3. No code changes needed!

The local backend uses the **exact same code** as Lambda, so what works locally will work in AWS.
