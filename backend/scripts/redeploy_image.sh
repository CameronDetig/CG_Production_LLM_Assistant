#!/bin/bash

# Rebuilds Docker image with automatic versioning and updates Lambda function
# Reads configuration from .env file
# Automatically increments version number based on latest ECR tag

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

echo "🔍 Checking for existing versions in ECR..."

# Get all version tags from ECR (format: v1, v2, v3, etc.)
LATEST_VERSION=$(aws ecr describe-images \
    --repository-name ${ECR_REPO_NAME} \
    --region ${ECR_REGION} \
    --query 'sort_by(imageDetails,& imagePushedAt)[-1].imageTags[?starts_with(@, `v`)] | [0]' \
    --output text 2>/dev/null || echo "none")

if [ "$LATEST_VERSION" == "none" ] || [ -z "$LATEST_VERSION" ]; then
    # No version tags found, start at v1
    NEW_VERSION="v1"
    echo "   No existing versions found. Starting at ${NEW_VERSION}"
else
    echo "   Latest version: ${LATEST_VERSION}"
    
    # Parse version number (e.g., v5 -> 5)
    VERSION_NUM=${LATEST_VERSION#v}
    
    # Increment version
    NEW_VERSION_NUM=$((VERSION_NUM + 1))
    
    # Construct new version
    NEW_VERSION="v${NEW_VERSION_NUM}"
    echo "   Incrementing to: ${NEW_VERSION}"
fi

echo ""
echo "🔨 Building Lambda Docker image..."
echo "   Repository: ${ECR_REPO_NAME}"
echo "   Version: ${NEW_VERSION}"
echo "   ECR URI: ${ECR_URI}"
echo ""

# Build docker image for AMD64
docker buildx build \
  --platform linux/amd64 \
  --provenance=false \
  --sbom=false \
  --load \
  -t ${ECR_REPO_NAME}:${NEW_VERSION} \
  -t ${ECR_REPO_NAME}:latest .

echo ""
echo "✅ Build complete"
echo "📤 Pushing to ECR..."

# Login to ECR
aws ecr get-login-password --region ${ECR_REGION} | \
    docker login --username AWS --password-stdin ${ECR_URI%/*}

# Tag with version and latest
docker tag ${ECR_REPO_NAME}:${NEW_VERSION} ${ECR_URI}:${NEW_VERSION}
docker tag ${ECR_REPO_NAME}:${NEW_VERSION} ${ECR_URI}:latest

# Push both tags
echo "   Pushing ${NEW_VERSION}..."
docker push ${ECR_URI}:${NEW_VERSION}
echo "   Pushing latest..."
docker push ${ECR_URI}:latest

echo ""
echo "✅ Push complete"
echo "🔄 Updating Lambda function to use ${NEW_VERSION}..."

# Note: Architecture must be set to arm64 in AWS Console or via AWS CLI v2
# The image is built for ARM64, so ensure Lambda is configured accordingly

# Update Lambda code with the versioned image
aws lambda update-function-code \
    --function-name ${LAMBDA_FUNCTION_NAME} \
    --image-uri ${ECR_URI}:${NEW_VERSION} \
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
    echo ""
    echo "🎉 Deployment successful!"
    echo "   Version: ${NEW_VERSION}"
    echo "   Image: ${ECR_URI}:${NEW_VERSION}"
else
    echo "⏳ Deployment in progress. Check AWS Console for status."
fi
