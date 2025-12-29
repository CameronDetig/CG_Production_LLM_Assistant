#!/bin/bash

# Lambda Deployment Script
# This script packages and deploys your Lambda function to AWS

set -e  # Exit on error

echo "=========================================="
echo "Lambda Function Deployment Script"
echo "=========================================="
echo ""

# Configuration
FUNCTION_NAME="cg-production-chatbot"
REGION="us-east-1"
RUNTIME="python3.11"
HANDLER="lambda_function.lambda_handler"
MEMORY_SIZE=512
TIMEOUT=30

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${RED}❌ AWS CLI is not installed${NC}"
    echo "Please install it: https://aws.amazon.com/cli/"
    exit 1
fi

echo -e "${GREEN}✅ AWS CLI found${NC}"

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  .env file not found${NC}"
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo -e "${YELLOW}Please edit .env with your actual values before deploying${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Environment file found${NC}"

# Create deployment package directory
echo ""
echo "Step 1: Creating deployment package..."
rm -rf package deployment.zip
mkdir -p package

# Install dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt -t package/ --quiet

# Copy Lambda function files
echo "Copying Lambda function files..."
cp lambda_function.py package/
cp bedrock_client.py package/
cp database.py package/

# Create ZIP file
echo "Creating deployment package (deployment.zip)..."
cd package
zip -r ../deployment.zip . -q
cd ..

echo -e "${GREEN}✅ Deployment package created ($(du -h deployment.zip | cut -f1))${NC}"

# Check if Lambda function exists
echo ""
echo "Step 2: Checking if Lambda function exists..."
if aws lambda get-function --function-name $FUNCTION_NAME --region $REGION &> /dev/null; then
    echo -e "${YELLOW}Function exists. Updating code...${NC}"
    
    aws lambda update-function-code \
        --function-name $FUNCTION_NAME \
        --zip-file fileb://deployment.zip \
        --region $REGION \
        --no-cli-pager
    
    echo -e "${GREEN}✅ Function code updated${NC}"
    
    # Update environment variables
    echo "Updating environment variables..."
    source .env
    aws lambda update-function-configuration \
        --function-name $FUNCTION_NAME \
        --environment "Variables={
            DB_HOST=$DB_HOST,
            DB_NAME=$DB_NAME,
            DB_USER=$DB_USER,
            DB_PASSWORD=$DB_PASSWORD,
            DB_PORT=$DB_PORT,
            AWS_REGION=$AWS_REGION,
            BEDROCK_MODEL_ID=$BEDROCK_MODEL_ID
        }" \
        --region $REGION \
        --no-cli-pager
    
    echo -e "${GREEN}✅ Environment variables updated${NC}"
    
else
    echo -e "${YELLOW}Function does not exist.${NC}"
    echo "Please create the Lambda function manually first (see README.md)"
    echo "Or run: ./create_lambda.sh"
fi

# Cleanup
echo ""
echo "Step 3: Cleaning up..."
rm -rf package

echo ""
echo -e "${GREEN}=========================================="
echo "✅ Deployment Complete!"
echo "==========================================${NC}"
echo ""
echo "Next steps:"
echo "1. Test your function in AWS Lambda console"
echo "2. Configure API Gateway (see README.md)"
echo "3. Update CORS settings with your Gradio URL"
echo ""
