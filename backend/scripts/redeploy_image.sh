#!/bin/bash

# Rebuilds Docker image and updates Lambda function
# Reads configuration from .env file

# to run, use
# cd backend
# bash scripts/redeploy_image.sh

set -e  # Exit on error

# Load environment variables from .env file
if [ -f .env ]; then
    echo "📄 Loading configuration from .env..."
    export $(grep -v '^#' .env | grep -v '^$' | xargs)
else
    echo "❌ Error: .env file not found!"
    echo "Please copy .env.example to .env and configure it."
    exit 1
fi

# Validate required variables
required_vars=("AWS_ACCOUNT_ID" "ECR_REGION" "ECR_REPO_NAME" "LAMBDA_FUNCTION_NAME")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "❌ Error: $var is not set in .env file"
        exit 1
    fi
done

# Construct ECR URI
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${ECR_REGION}.amazonaws.com/${ECR_REPO_NAME}"

echo "🔨 Rebuilding Lambda Docker image..."
echo "   Repository: ${ECR_REPO_NAME}"
echo "   ECR URI: ${ECR_URI}:latest"
echo ""

# Build docker image
docker buildx build \
  --platform linux/amd64 \
  --provenance=false \
  --sbom=false \
  --load \
  -t ${ECR_REPO_NAME} .

echo ""
echo "✅ Build complete"
echo "📤 Pushing to ECR..."

# Login to ECR
aws ecr get-login-password --region ${ECR_REGION} | \
    docker login --username AWS --password-stdin ${ECR_URI%/*}

# Tag and push
docker tag ${ECR_REPO_NAME}:latest ${ECR_URI}:latest
docker push ${ECR_URI}:latest

echo ""
echo "✅ Push complete"
echo "🔄 Updating Lambda function..."

# Update Lambda
aws lambda update-function-code \
    --function-name ${LAMBDA_FUNCTION_NAME} \
    --image-uri ${ECR_URI}:latest \
    --region ${ECR_REGION} \
    --no-cli-pager

echo ""
echo "✅ Lambda updated! Waiting for deployment to complete..."

# Wait for update to finish
sleep 5
status=$(aws lambda get-function \
    --function-name ${LAMBDA_FUNCTION_NAME} \
    --region ${ECR_REGION} \
    --query 'Configuration.LastUpdateStatus' \
    --output text)

echo "   Status: ${status}"

if [ "$status" == "Successful" ]; then
    echo "🎉 Deployment successful!"
else
    echo "⏳ Deployment in progress. Check AWS Console for status."
fi
