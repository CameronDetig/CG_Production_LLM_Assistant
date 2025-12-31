#!/bin/bash

# Infrastructure Setup Script for CG Production LLM Assistant
# This script automates the creation of S3, DynamoDB, and Cognito resources

set -e  # Exit on error

echo "CG Production LLM Assistant - Infrastructure Setup"
echo "======================================================"
echo ""

# Get AWS Account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION="us-east-1"

echo "AWS Account ID: $AWS_ACCOUNT_ID"
echo "Region: $REGION"
echo ""

# ============================================================================
# S3 Thumbnail Bucket
# ============================================================================

echo "📦 Step 1: Creating S3 Thumbnail Bucket..."

if aws s3 ls s3://cg-production-data-thumbnails 2>/dev/null; then
    echo "✅ S3 bucket 'cg-production-data-thumbnails' already exists"
else
    aws s3 mb s3://cg-production-data-thumbnails --region $REGION
    echo "✅ Created S3 bucket 'cg-production-data-thumbnails'"
fi

# Create folder structure
echo "📁 Creating folder structure (blend, images, videos)..."
touch .placeholder
aws s3 cp .placeholder s3://cg-production-data-thumbnails/blend/.placeholder 2>/dev/null || true
aws s3 cp .placeholder s3://cg-production-data-thumbnails/images/.placeholder 2>/dev/null || true
aws s3 cp .placeholder s3://cg-production-data-thumbnails/videos/.placeholder 2>/dev/null || true
rm .placeholder
echo "✅ Folder structure created"

# Apply bucket policy
echo "🔒 Applying S3 bucket policy..."
cat > /tmp/thumbnail_bucket_policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowLambdaReadAccess",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::${AWS_ACCOUNT_ID}:role/cg-chatbot-lambda-role"
      },
      "Action": [
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::cg-production-data-thumbnails/*"
    }
  ]
}
EOF

aws s3api put-bucket-policy \
  --bucket cg-production-data-thumbnails \
  --policy file:///tmp/thumbnail_bucket_policy.json

echo "✅ S3 bucket policy applied"
echo ""

# ============================================================================
# DynamoDB Conversations Table
# ============================================================================

echo "Step 2: Creating DynamoDB Conversations Table..."

if aws dynamodb describe-table --table-name cg-chatbot-conversations --region $REGION 2>/dev/null; then
    echo "✅ DynamoDB table 'cg-chatbot-conversations' already exists"
else
    cat > /tmp/dynamodb-table.json << 'EOF'
{
  "TableName": "cg-chatbot-conversations",
  "KeySchema": [
    {
      "AttributeName": "conversation_id",
      "KeyType": "HASH"
    },
    {
      "AttributeName": "user_id",
      "KeyType": "RANGE"
    }
  ],
  "AttributeDefinitions": [
    {
      "AttributeName": "conversation_id",
      "AttributeType": "S"
    },
    {
      "AttributeName": "user_id",
      "AttributeType": "S"
    },
    {
      "AttributeName": "created_at",
      "AttributeType": "S"
    }
  ],
  "GlobalSecondaryIndexes": [
    {
      "IndexName": "user_id-created_at-index",
      "KeySchema": [
        {
          "AttributeName": "user_id",
          "KeyType": "HASH"
        },
        {
          "AttributeName": "created_at",
          "KeyType": "RANGE"
        }
      ],
      "Projection": {
        "ProjectionType": "ALL"
      }
    }
  ],
  "BillingMode": "PAY_PER_REQUEST",
  "Tags": [
    {
      "Key": "Project",
      "Value": "CG-Production-Assistant"
    }
  ]
}
EOF

    aws dynamodb create-table --cli-input-json file:///tmp/dynamodb-table.json --region $REGION
    echo "⏳ Waiting for table to be active..."
    aws dynamodb wait table-exists --table-name cg-chatbot-conversations --region $REGION
    echo "✅ DynamoDB table created"
fi

echo ""

# ============================================================================
# AWS Cognito User Pool
# ============================================================================

echo "Step 3: Creating Cognito User Pool..."

# Check if user pool exists
USER_POOL_ID=$(aws cognito-idp list-user-pools --max-results 50 --region $REGION \
  --query "UserPools[?Name=='cg-production-assistant-users'].Id" --output text)

if [ -n "$USER_POOL_ID" ]; then
    echo "✅ User pool 'cg-production-assistant-users' already exists"
    echo "   User Pool ID: $USER_POOL_ID"
else
    USER_POOL_ID=$(aws cognito-idp create-user-pool \
      --pool-name cg-production-assistant-users \
      --policies "PasswordPolicy={MinimumLength=8,RequireUppercase=true,RequireLowercase=true,RequireNumbers=true,RequireSymbols=true}" \
      --auto-verified-attributes email \
      --username-attributes email \
      --region $REGION \
      --query 'UserPool.Id' --output text)
    
    echo "✅ Created user pool: $USER_POOL_ID"
fi

# Create app client
CLIENT_ID=$(aws cognito-idp list-user-pool-clients --user-pool-id $USER_POOL_ID --region $REGION \
  --query "UserPoolClients[?ClientName=='cg-assistant-client'].ClientId" --output text)

if [ -n "$CLIENT_ID" ]; then
    echo "✅ App client 'cg-assistant-client' already exists"
    echo "   Client ID: $CLIENT_ID"
else
    CLIENT_ID=$(aws cognito-idp create-user-pool-client \
      --user-pool-id $USER_POOL_ID \
      --client-name cg-assistant-client \
      --no-generate-secret \
      --explicit-auth-flows ALLOW_USER_PASSWORD_AUTH ALLOW_REFRESH_TOKEN_AUTH \
      --region $REGION \
      --query 'UserPoolClient.ClientId' --output text)
    
    echo "✅ Created app client: $CLIENT_ID"
fi

# Create demo user
echo "👤 Creating demo user..."
if aws cognito-idp admin-get-user --user-pool-id $USER_POOL_ID --username demo@cgassistant.com --region $REGION 2>/dev/null; then
    echo "✅ Demo user already exists"
else
    aws cognito-idp admin-create-user \
      --user-pool-id $USER_POOL_ID \
      --username demo@cgassistant.com \
      --user-attributes Name=email,Value=demo@cgassistant.com Name=email_verified,Value=true \
      --message-action SUPPRESS \
      --region $REGION
    
    aws cognito-idp admin-set-user-password \
      --user-pool-id $USER_POOL_ID \
      --username demo@cgassistant.com \
      --password "DemoPass10!" \
      --permanent \
      --region $REGION
    
    echo "✅ Demo user created (demo@cgassistant.com / DemoPass10!)"
fi

echo ""

# ============================================================================
# Update Lambda IAM Role
# ============================================================================

echo "Step 4: Updating Lambda IAM Role..."

# Apply updated IAM policy
aws iam put-role-policy \
  --role-name cg-chatbot-lambda-role \
  --policy-name CG-Chatbot-Permissions \
  --policy-document file://iam_policy.json

echo "✅ Lambda IAM role updated with S3, DynamoDB, and Bedrock permissions"
echo ""

# ============================================================================
# Update Lambda Environment Variables
# ============================================================================

echo "Step 5: Updating Lambda Environment Variables..."

# Get current environment variables
CURRENT_ENV=$(aws lambda get-function-configuration \
  --function-name cg-production-chatbot \
  --region $REGION \
  --query 'Environment.Variables' \
  --output json 2>/dev/null || echo '{}')

# Merge with new variables using jq
NEW_ENV=$(echo $CURRENT_ENV | jq \
  --arg bucket "cg-production-data-thumbnails" \
  --arg table "cg-chatbot-conversations" \
  --arg pool "$USER_POOL_ID" \
  --arg client "$CLIENT_ID" \
  --arg region "$REGION" \
  '. + {
    THUMBNAIL_BUCKET: $bucket,
    DYNAMODB_TABLE_NAME: $table,
    COGNITO_USER_POOL_ID: $pool,
    COGNITO_CLIENT_ID: $client,
    COGNITO_REGION: $region
  }')

aws lambda update-function-configuration \
  --function-name cg-production-chatbot \
  --environment "Variables=$NEW_ENV" \
  --region $REGION > /dev/null

echo "✅ Lambda environment variables updated"
echo ""

# ============================================================================
# Summary
# ============================================================================

echo "✨ Infrastructure Setup Complete!"
echo "=================================="
echo ""
echo "📋 Configuration Summary:"
echo "  S3 Bucket: cg-production-data-thumbnails"
echo "  DynamoDB Table: cg-chatbot-conversations"
echo "  Cognito User Pool ID: $USER_POOL_ID"
echo "  Cognito Client ID: $CLIENT_ID"
echo "  Demo Account: demo@cgassistant.com / DemoPass10!"
echo ""
echo "📝 Next Steps:"
echo "  1. Upload thumbnails to S3 (if you have them):"
echo "     aws s3 sync ./thumbnails/ s3://cg-production-data-thumbnails/"
echo ""
echo "  2. Implement backend modules:"
echo "     - s3_utils.py"
echo "     - conversations.py"
echo "     - auth.py"
echo ""
echo "  3. Test infrastructure:"
echo "     python test_local.py"
echo ""
echo "🎉 You're ready to proceed with Phase 2!"
