# Container Deployment Guide

This guide provides step-by-step instructions for deploying the Lambda function using Docker containers.

## Prerequisites

- Docker installed and running
- AWS CLI configured with credentials
- AWS account ID

## Step 1: Set Environment Variables

Using a bash shell (Linux, macOS, WSL):

```bash
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export REGION="us-east-1"
export REPO_NAME="cg-chatbot"
export FUNCTION_NAME="cg-production-chatbot"
```

## Step 2: Create ECR Repository

```bash
aws ecr create-repository \
    --repository-name $REPO_NAME \
    --region $REGION
```

## Step 3: Build Docker Image

**Important**: Use `docker buildx` with specific flags to ensure Lambda compatibility:

```bash
cd backend
docker buildx build \
  --platform linux/amd64 \
  --provenance=false \
  --sbom=false \
  --load \
  -t $REPO_NAME .
```

> **Why these flags?** AWS Lambda requires Docker v2 manifest format. Without `--provenance=false` and `--sbom=false`, Docker creates OCI manifests that Lambda rejects.

This will:
- Build for x86_64 architecture (required for standard Lambda)
- Install Python dependencies using multi-stage build
- Copy Lambda function code
- Set up the Lambda runtime environment

**Build time**: ~15-20 minutes first time (downloads PyTorch ~2GB + models ~500MB)

## Step 4: Authenticate with ECR

```bash
aws ecr get-login-password --region $REGION | \
    docker login --username AWS --password-stdin \
    $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com
```

## Step 5: Tag and Push Image

```bash
# Tag image
docker tag $REPO_NAME:latest \
    $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO_NAME:latest

# Push to ECR
docker push $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO_NAME:latest
```

**Upload time**: ~2-5 minutes depending on internet speed

## Step 6: Update Lambda Function

```bash
aws lambda update-function-code \
    --function-name $FUNCTION_NAME \
    --image-uri $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO_NAME:latest \
    --region $REGION
```

## Step 7: Configure Lambda Settings

```bash
# Increase memory and timeout for embedding models
aws lambda update-function-configuration \
    --function-name $FUNCTION_NAME \
    --memory-size 2048 \
    --timeout 60 \
    --region $REGION
```

> **Note**: 2048 MB memory is recommended for loading embedding models efficiently.

## Step 8: Set Environment Variables

```bash
# Source your .env file or set variables manually
aws lambda update-function-configuration \
    --function-name $FUNCTION_NAME \
    --environment "Variables={
        DB_HOST=your-rds-endpoint.us-east-1.rds.amazonaws.com
        DB_NAME=your_database_name
        DB_USER=your_username
        DB_PASSWORD=your_password
        DB_PORT=5432
        BEDROCK_MODEL_ID=meta.llama3-2-11b-instruct-v1:0
        THUMBNAIL_BUCKET=cg-production-data-thumbnails
        COGNITO_USER_POOL_ID=us-east-1_abc123xyz
        COGNITO_CLIENT_ID=your-client-id
        COGNITO_REGION=us-east-1
    }" \
    --region $REGION
```

### Under Configuration > RDS databases:
add a connection to the cg-metadate-db database

> **Note**: `AWS_REGION` is automatically set by Lambda and cannot be overridden. Your code will use the region where the Lambda function is deployed.

## Step 9: Test the Function

```bash
# Create test event
cat > test-event.json <<EOF
{
  "body": "{\"query\": \"Show me recent renders\", \"user_id\": \"test\"}"
}
EOF

# Invoke function
aws lambda invoke \
    --function-name $FUNCTION_NAME \
    --payload file://test-event.json \
    --region $REGION \
    response.json

# View response
cat response.json
```

## Updating the Function

When you make code changes that require a new image to be built, follow these steps:

```bash
# Rebuild image with Lambda-compatible manifest
docker buildx build --platform linux/amd64 --provenance=false --sbom=false --load -t $REPO_NAME .

# Tag and push
docker tag $REPO_NAME:latest \
    $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO_NAME:latest

docker push $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO_NAME:latest

# Update Lambda
aws lambda update-function-code \
    --function-name $FUNCTION_NAME \
    --image-uri $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO_NAME:latest \
    --region $REGION
```

## Troubleshooting

### "Image manifest, config or layer media type is not supported"

This error occurs when Lambda receives an OCI manifest instead of Docker v2 format.

**Solution**: Rebuild with the correct flags:
```bash
docker buildx build \
  --platform linux/amd64 \
  --provenance=false \
  --sbom=false \
  --load \
  -t $REPO_NAME .
```

Then re-tag and push to ECR.

### Build fails with "no space left on device"
```bash
# Clean up Docker
docker system prune -a
```

### Lambda timeout errors
```bash
# Increase timeout to 90 seconds
aws lambda update-function-configuration \
    --function-name $FUNCTION_NAME \
    --timeout 90 \
    --region $REGION
```

### Out of memory errors
```bash
# Increase memory to 3008 MB (max)
aws lambda update-function-configuration \
    --function-name $FUNCTION_NAME \
    --memory-size 3008 \
    --region $REGION
```

### Cold start too slow
- First request after deployment takes 10-15 seconds (model loading)
- Consider using Lambda Provisioned Concurrency for production
- Or implement lazy loading (load models only when needed)

## Cost Optimization

- **ECR Storage**: ~$0.10/GB/month (~$0.05/month for this image)
- **Lambda**: Same pricing as ZIP deployment
- **Tip**: Delete old ECR images to save storage costs

```bash
# List images
aws ecr list-images --repository-name $REPO_NAME --region $REGION

# Delete specific image
aws ecr batch-delete-image \
    --repository-name $REPO_NAME \
    --image-ids imageTag=old-tag \
    --region $REGION
```
