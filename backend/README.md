# Quick Start Guide - Lambda Backend

## Overview

Production-ready Lambda chatbot backend with semantic search for CG production assets.

**Key Features:**
- ✅ Semantic text search (all-MiniLM-L6-v2, 384 dims)
- ✅ Visual search with CLIP (512 dims) 
- ✅ Streaming AI responses (Llama 3.2 via Bedrock)
- ✅ Hybrid search (semantic + keyword fallback)

---

## Database Schema

### Main Table: `files`
Core metadata + `metadata_embedding` (Vector 384)

### Type-Specific Tables:
- `images` - width, height, mode, `visual_embedding` (Vector 512)
- `videos` - duration, fps, codec, `visual_embedding` (Vector 512)
- `blend_files` - render_engine, resolution, objects, `visual_embedding` (Vector 512)

See [docs/SCHEMA.md](docs/SCHEMA.md) for details.

---

## Files Created

| File | Purpose |
|------|---------|
| `lambda_function.py` | Main Lambda handler with SSE streaming |
| `database.py` | PostgreSQL queries with pgvector search |
| `embeddings.py` | Text & image embedding generation |
| `bedrock_client.py` | Llama model integration |
| `requirements.txt` | Python dependencies |
| `Dockerfile` | Container deployment config |
| `.env.example` | Environment variables template |
| `iam_policy.json` | IAM permissions |
| `SCHEMA.md` | Database documentation |

---

## Deployment (Container Required)

### Why Container?
Embedding models (~500MB) exceed Lambda's 250MB ZIP limit.

### Quick Deploy

```bash
# Set variables
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export REGION="us-east-1"
export REPO_NAME="cg-chatbot"

# Create ECR repo
aws ecr create-repository --repository-name $REPO_NAME --region $REGION

# Build and push
docker build -t $REPO_NAME .
aws ecr get-login-password --region $REGION | \
    docker login --username AWS --password-stdin \
    $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com

docker tag $REPO_NAME:latest \
    $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO_NAME:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO_NAME:latest

# Update Lambda
aws lambda update-function-code \
    --function-name cg-production-chatbot \
    --image-uri $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO_NAME:latest
```

---

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and fill in:

```bash
DB_HOST=your-rds-endpoint.us-east-1.rds.amazonaws.com
DB_NAME=your_database_name
DB_USER=your_username
DB_PASSWORD=your_password
DB_PORT=5432
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=us.meta.llama3-2-11b-instruct-v1:0
```

### Lambda Settings

- **Memory**: 2048 MB (for embedding models)
- **Timeout**: 60 seconds
- **Runtime**: Container (Python 3.11 base)

---

## Testing

### Local Test

```bash
pip install -r requirements.txt python-dotenv
cp .env.example .env
# Edit .env with your credentials
python test_local.py
```

### API Test

```bash
curl -X POST https://your-api-id.execute-api.us-east-1.amazonaws.com/prod/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Show me Blender files with Cycles renders"}'
```

---

## How It Works

### Query Flow

1. **User Query** → API Gateway
2. **Generate Embedding** (all-MiniLM-L6-v2)
3. **Vector Search** (pgvector cosine similarity on `files.metadata_embedding`)
4. **Build Context** (format metadata for Llama)
5. **Stream Response** (Bedrock Llama 3.2 via SSE)

### Search Strategies

**Semantic Search** (default):
```sql
SELECT * FROM files
WHERE metadata_embedding IS NOT NULL
ORDER BY metadata_embedding <=> query_embedding
LIMIT 10
```

**Visual Search**:
```sql
SELECT * FROM images/videos/blend_files
WHERE visual_embedding IS NOT NULL
ORDER BY visual_embedding <=> clip_embedding
LIMIT 10
```

**Keyword Fallback**:
```sql
SELECT * FROM files
WHERE file_name ILIKE '%keyword%'
   OR metadata_json::text ILIKE '%keyword%'
```

---

## Cost Estimate

**Monthly (1,000 queries):**
- Lambda: ~$0.50
- API Gateway: ~$0.004
- Bedrock (Llama 3.2 11B): ~$1.13
- RDS PostgreSQL: ~$15
- ECR Storage: ~$0.05
- **Total: ~$16.67/month**

---

## Next Steps

1. ✅ Deploy Lambda function (container)
2. ⏳ Build Gradio frontend
3. ⏳ Create Blender plugin
4. ⏳ Test end-to-end workflow

---

## Troubleshooting

**Cold start slow?**
- First request loads models (~10-15s)
- Subsequent requests are fast (<2s)
- Consider Provisioned Concurrency for production

**Database connection errors?**
- Check RDS security group allows Lambda
- Verify environment variables
- Check CloudWatch logs

**Bedrock access denied?**
- Enable model access in Bedrock console
- Check IAM policy includes `bedrock:InvokeModelWithResponseStream`

---

## Support

- **Schema**: [docs/SCHEMA.md](docs/SCHEMA.md)
- **Deployment**: See Dockerfile and deploy commands above
- **Logs**: CloudWatch → Lambda → cg-production-chatbot
