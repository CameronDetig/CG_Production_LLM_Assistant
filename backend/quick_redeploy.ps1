# Quick Lambda Redeploy Script
# Rebuilds Docker image and updates Lambda function

Write-Host "🔨 Rebuilding Lambda Docker image..." -ForegroundColor Cyan

# Build with no cache to ensure fresh build
docker buildx build --platform linux/amd64 --provenance=false --sbom=false --no-cache --load -t cg-chatbot .

Write-Host "✅ Build complete" -ForegroundColor Green
Write-Host "📤 Pushing to ECR..." -ForegroundColor Cyan

# Tag and push
docker tag cg-chatbot:latest REDACTED_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/cg-chatbot:latest
docker push REDACTED_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/cg-chatbot:latest

Write-Host "✅ Push complete" -ForegroundColor Green
Write-Host "🔄 Updating Lambda function..." -ForegroundColor Cyan

# Update Lambda
aws lambda update-function-code `
    --function-name cg-production-chatbot `
    --image-uri REDACTED_AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/cg-chatbot:latest `
    --region us-east-1 `
    --no-cli-pager

Write-Host "✅ Lambda updated! Wait 30 seconds for deployment to complete." -ForegroundColor Green
