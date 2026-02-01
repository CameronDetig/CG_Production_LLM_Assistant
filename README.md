# CG Production LLM Assistant

AWS Lambda backend for AI chatbot with Bedrock (Llama 3.2) and PostgreSQL integration.
Providing information on a database of CG production assets based on natural language queries.

## 📋 Table of Contents

- [Architecture Overview](#architecture-overview)
- [Prerequisites](#prerequisites)
- [AWS Setup Guide (Step-by-Step)](#aws-setup-guide-step-by-step)
- [Local Development](#local-development)
- [Deployment](#deployment)
- [API Documentation](#api-documentation)
- [Troubleshooting](#troubleshooting)
- [Cost Monitoring](#cost-monitoring)

---

## 🏗️ Architecture Overview

```
Gradio UI (Hugging Face) → API Gateway → Lambda → Bedrock LLMs
                                          ↓
                                    PostgreSQL (RDS)
```

**Components:**
- **Lambda Function**: Handles chatbot logic, streaming responses, semantic search
- **Amazon Bedrock**: Llama 3.2 11B Instruct model for AI responses
- **RDS PostgreSQL with pgvector**: Stores Blender file metadata + embeddings
- **Embedding Models**: sentence-transformers (text) + CLIP (images)
- **API Gateway**: REST API with Server-Sent Events (SSE) for streaming

---

## ✅ Prerequisites

### Required Accounts & Tools

1. **AWS Account** - [Sign up here](https://aws.amazon.com/)
2. **AWS CLI** - [Installation guide](https://aws.amazon.com/cli/)
3. **Python 3.11+** - [Download](https://www.python.org/downloads/)
4. **Git** - [Download](https://git-scm.com/downloads)

### Required AWS Services Access

- Amazon Bedrock (Llama models)
- AWS Lambda
- Amazon RDS (PostgreSQL)
- Amazon API Gateway
- IAM (for permissions)

---

## 🚀 AWS Setup Guide (Step-by-Step)

### Step 1: Enable Amazon Bedrock Models

> **Important**: Bedrock models must be enabled before use.

1. **Log into AWS Console**: https://console.aws.amazon.com/
2. **Navigate to Bedrock**:
   - Search for "Bedrock" in the top search bar
   - Click "Amazon Bedrock"
3. **Select Region**: Make sure you're in **us-east-1** (top-right corner)
4. **Enable Model Access**:
   - Click "Model access" in the left sidebar
   - Click "Manage model access" (orange button)
   - Find **Meta** section
   - Check the boxes for:
     - ✅ Llama 3.2 11B Instruct
     - ✅ Llama 3.1 70B Instruct (optional, for complex queries)
   - Click "Request model access" at the bottom
   - Wait 1-2 minutes for approval (usually instant)

5. **Verify Access**:
   - Refresh the page
   - Status should show "Access granted" (green)

---

### Step 2: Set Up PostgreSQL Database (RDS)

> **Note**: If you already have your RDS PostgreSQL database set up, skip to Step 3.

1. **Navigate to RDS**:
   - Search for "RDS" in AWS Console
   - Click "Amazon RDS"

2. **Create Database**:
   - Click "Create database" (orange button)
   - Choose:
     - **Engine**: PostgreSQL
     - **Version**: PostgreSQL 15.x or later
     - **Template**: Free tier (if eligible) or Dev/Test
     - **DB instance identifier**: `cg-production-db`
     - **Master username**: `postgres` (or your choice)
     - **Master password**: Create a strong password (save this!)
   
3. **Configure Instance**:
   - **Instance class**: `db.t3.micro` (cheapest, ~$15/month)
   - **Storage**: 20 GB (default)
   - **Public access**: Yes (for now, for easier setup)
   - **VPC security group**: Create new → name it `cg-db-security-group`

4. **Create Database**:
   - Click "Create database"
   - Wait 5-10 minutes for creation

5. **Get Connection Details**:
   - Click on your database name
   - Under "Connectivity & security":
     - Copy **Endpoint** (e.g., `cg-production-db.xxxxx.us-east-1.rds.amazonaws.com`)
     - Note **Port** (usually `5432`)
   - Save these for later!

6. **Configure Security Group**:
   - Click on the VPC security group link
   - Click "Edit inbound rules"
   - Add rule:
     - **Type**: PostgreSQL
     - **Source**: My IP (for testing) or Custom (Lambda's security group later)
   - Click "Save rules"

---

### Step 3: Create IAM Role for Lambda

Lambda needs permissions to access Bedrock and RDS.

1. **Navigate to IAM**:
   - Search for "IAM" in AWS Console
   - Click "Roles" in left sidebar

2. **Create Role**:
   - Click "Create role"
   - **Trusted entity**: AWS service
   - **Use case**: Lambda
   - Click "Next"

3. **Attach Policies**:
   - Search and select these AWS managed policies:
     - ✅ `AWSLambdaBasicExecutionRole` (for CloudWatch logs)
     - ✅ `AWSLambdaVPCAccessExecutionRole` (for RDS access)
   - Click "Next"

4. **Name the Role**:
   - **Role name**: `cg-chatbot-lambda-role`
   - Click "Create role"

5. **Add Custom Bedrock Policy**:
   - Click on your new role
   - Click "Add permissions" → "Create inline policy"
   - Click "JSON" tab
   - Paste the contents of `iam_policy.json` from this repo
   - Click "Review policy"
   - **Name**: `BedrockAccess`
   - Click "Create policy"

---

### Step 4: Create Lambda Function

1. **Navigate to Lambda**:
   - Search for "Lambda" in AWS Console
   - Make sure you're in **us-east-1** region

2. **Create Function**:
   - Click "Create function"
   - Choose "Author from scratch"
   - **Function name**: `cg-production-chatbot`
   - **Runtime**: Python 3.11
   - **Architecture**: x86_64
   - **Permissions**: Use existing role → select `cg-chatbot-lambda-role`
   - Click "Create function"

3. **Configure Function**:
   - Scroll to "Configuration" tab
   - Click "General configuration" → "Edit"
     - **Memory**: 512 MB
     - **Timeout**: 30 seconds
   - Click "Save"

4. **Set Environment Variables**:
   - Click "Configuration" → "Environment variables" → "Edit"
   - Add these variables (use your actual values):
     ```
     DB_HOST = your-rds-endpoint.us-east-1.rds.amazonaws.com
     DB_NAME = your_database_name
     DB_USER = postgres
     DB_PASSWORD = your_password
     DB_PORT = 5432
     AWS_REGION = us-east-1
     BEDROCK_MODEL_ID = meta.llama3-2-11b-instruct-v1:0
     ```
   - Click "Save"

5. **Deploy Code** (we'll do this in the Deployment section below)

---

### Step 5: Create API Gateway

1. **Navigate to API Gateway**:
   - Search for "API Gateway" in AWS Console

2. **Create API**:
   - Click "Create API"
   - Choose "REST API" (not private)
   - Click "Build"
   - **API name**: `cg-chatbot-api`
   - **Endpoint Type**: Regional
   - Click "Create API"

3. **Create Resource**:
   - Click "Actions" → "Create Resource"
   - **Resource Name**: `chat`
   - **Resource Path**: `/chat`
   - ✅ Enable CORS
   - Click "Create Resource"

4. **Create POST Method**:
   - Select `/chat` resource
   - Click "Actions" → "Create Method"
   - Choose "POST" from dropdown
   - Click the checkmark ✓
   - **Integration type**: Lambda Function
   - ✅ Use Lambda Proxy integration
   - **Lambda Function**: `cg-production-chatbot`
   - Click "Save"
   - Click "OK" on the permission popup

5. **Enable CORS** (for Gradio):
   - Select `/chat` resource
   - Click "Actions" → "Enable CORS"
   - Use default settings
   - Click "Enable CORS and replace existing CORS headers"
   - Click "Yes, replace existing values"

6. **Deploy API**:
   - Click "Actions" → "Deploy API"
   - **Deployment stage**: [New Stage]
   - **Stage name**: `prod`
   - Click "Deploy"

7. **Get API URL**:
   - You'll see "Invoke URL" at the top
   - Copy this URL (e.g., `https://abc123.execute-api.us-east-1.amazonaws.com/prod`)
   - Your endpoint will be: `{Invoke URL}/chat`
   - **Save this URL!** You'll need it for Gradio

---

## 💻 Local Development

### 1. Clone Repository & Install Dependencies

```bash
cd backend
pip install -r requirements.txt
pip install python-dotenv  # For local testing
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your actual values
nano .env  # or use any text editor
```

Fill in your PostgreSQL and AWS details.

### 3. Test Locally

```bash
# Run local tests
python test_local.py
```

This will test:
- ✅ Database connectivity
- ✅ Bedrock API access
- ✅ Full Lambda function flow

---

## 🚢 Deployment

### Recommended: Container Deployment

> [!WARNING]
> **ZIP deployment will not work** due to large embedding models (~500MB). You must use container deployment.

#### Step 1: Build Docker Image

```bash
# Install dependencies to package directory
pip install -r requirements.txt -t package/

# Copy function files
cp lambda_function.py bedrock_client.py database.py package/

# Create ZIP file
cd package
zip -r ../deployment.zip .
cd ..

# Upload to Lambda (using AWS CLI)
aws lambda update-function-code \
    --function-name cg-production-chatbot \
    --zip-file fileb://deployment.zip \
    --region us-east-1
```

#### Step 2: Create ECR Repository

```bash
# Get your AWS account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION="us-east-1"
REPO_NAME="cg-chatbot"

# Create ECR repository
aws ecr create-repository --repository-name $REPO_NAME --region $REGION
```

#### Step 3: Authenticate Docker with ECR

```bash
# Login to ECR
aws ecr get-login-password --region $REGION | \
    docker login --username AWS --password-stdin \
    $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com
```

#### Step 4: Build and Push Image

```bash
# Build Docker image
docker build -t $REPO_NAME .

# Tag for ECR
docker tag $REPO_NAME:latest \
    $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO_NAME:latest

# Push to ECR
docker push $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO_NAME:latest
```

#### Step 5: Update Lambda Function

```bash
# Update Lambda to use container image
aws lambda update-function-code \
    --function-name cg-production-chatbot \
    --image-uri $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO_NAME:latest
```

> [!TIP]
> **Cold Start Optimization**: The first request after deployment may take 10-15 seconds due to model loading. Subsequent requests will be much faster as models are cached in Lambda memory.

---

## 📡 API Documentation

### Endpoint

```
POST https://your-api-id.execute-api.us-east-1.amazonaws.com/prod/chat
```

### Request Format

```json
{
  "query": "Show me all 4K renders from the lighting project",
  "user_id": "optional-user-id"
}
```

### Response Format (Server-Sent Events)

```
data: {"type": "start", "metadata_count": 5}

data: {"type": "chunk", "text": "I found "}

data: {"type": "chunk", "text": "3 files "}

data: {"type": "chunk", "text": "matching your criteria..."}

data: {"type": "metadata", "files": [{...}, {...}]}

data: {"type": "end"}
```

### Testing with cURL

```bash
curl -X POST https://your-api-id.execute-api.us-east-1.amazonaws.com/prod/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Show me recent renders"}'
```

---

## 🔧 Troubleshooting

### Common Issues

#### 1. "AccessDeniedException" from Bedrock

**Solution**: Make sure you've enabled model access in Bedrock console (Step 1 above)

#### 2. Database Connection Timeout

**Solutions**:
- Check RDS security group allows Lambda's IP
- Verify database is publicly accessible (for testing)
- Check environment variables are correct

#### 3. Lambda Timeout

**Solutions**:
- Increase timeout in Lambda configuration (max 15 minutes)
- Optimize database queries
- Use smaller Bedrock model

#### 4. "Module not found" Error

**Solution**: Make sure dependencies are in the deployment package:
```bash
pip install -r requirements.txt -t package/
```

### Viewing Logs

1. Go to Lambda console
2. Click "Monitor" tab
3. Click "View CloudWatch logs"
4. Check recent log streams for errors

---

## 💰 Cost Monitoring

### Expected Monthly Costs (1,000 queries/month)

| Service | Cost |
|---------|------|
| Lambda | ~$0.30 |
| API Gateway | ~$0.004 |
| Bedrock (Llama 3.2 11B) | ~$1.13 |
| RDS PostgreSQL (t3.micro) | ~$15 |
| **Total** | **~$16.43/month** |

### Cost Optimization Tips

1. **Use RDS Proxy** - Reduce connection overhead
2. **Cache common queries** - Store in Lambda memory
3. **Use smaller model** - Llama 3.2 11B instead of 70B
4. **Set up billing alerts**:
   - AWS Console → Billing → Budgets
   - Create budget with $20 threshold
   - Get email alerts when exceeded

### Monitor Costs

```bash
# Check current month costs (AWS CLI)
aws ce get-cost-and-usage \
    --time-period Start=2024-01-01,End=2024-01-31 \
    --granularity MONTHLY \
    --metrics BlendedCost \
    --group-by Type=SERVICE
```

---

## 🔮 Future Enhancements

### Vector Search (pgvector)

Enable semantic search:

```sql
-- In your PostgreSQL database
CREATE EXTENSION vector;

ALTER TABLE media_metadata 
ADD COLUMN embedding vector(1536);
```

Uncomment `get_similar_files_vector()` in `database.py`.

### Conversation Storage (DynamoDB)

Uncomment `store_conversation()` in `lambda_function.py` and create DynamoDB table.

### Model Routing

Use `select_model()` in `bedrock_client.py` to automatically choose between Llama 11B and 70B based on query complexity.

---

## 📞 Support

For issues or questions:
1. Check CloudWatch logs
2. Review [AWS Lambda documentation](https://docs.aws.amazon.com/lambda/)
3. Review [Amazon Bedrock documentation](https://docs.aws.amazon.com/bedrock/)

---

## 📄 License

MIT License - See LICENSE file for details
