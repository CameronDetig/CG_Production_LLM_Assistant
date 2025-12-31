#!/bin/bash
# DynamoDB VPC Endpoint Setup Script
# This script automates the creation of a VPC endpoint for DynamoDB

set -e  # Exit on error

echo "🚀 DynamoDB VPC Endpoint Setup"
echo "================================"
echo ""

# Configuration
FUNCTION_NAME="cg-production-chatbot"
REGION="us-east-1"

# Step 1: Get Lambda VPC configuration
echo "Step 1: Getting Lambda VPC configuration..."
VPC_CONFIG=$(aws lambda get-function-configuration \
    --function-name $FUNCTION_NAME \
    --region $REGION \
    --query 'VpcConfig.{VpcId:VpcId,SubnetIds:SubnetIds}' \
    --output json)

VPC_ID=$(echo $VPC_CONFIG | jq -r '.VpcId')

if [ "$VPC_ID" == "null" ] || [ -z "$VPC_ID" ]; then
    echo "❌ Error: Lambda is not in a VPC"
    exit 1
fi

echo "✅ Found VPC: $VPC_ID"
echo ""

# Step 2: Get route table IDs
echo "Step 2: Getting route table IDs..."
ROUTE_TABLES=$(aws ec2 describe-route-tables \
    --filters "Name=vpc-id,Values=$VPC_ID" \
    --query 'RouteTables[*].RouteTableId' \
    --region $REGION \
    --output text)

if [ -z "$ROUTE_TABLES" ]; then
    echo "❌ Error: No route tables found for VPC $VPC_ID"
    exit 1
fi

echo "✅ Found route tables: $ROUTE_TABLES"
echo ""

# Step 3: Check if endpoint already exists
echo "Step 3: Checking for existing DynamoDB endpoint..."
EXISTING_ENDPOINT=$(aws ec2 describe-vpc-endpoints \
    --filters "Name=vpc-id,Values=$VPC_ID" "Name=service-name,Values=com.amazonaws.$REGION.dynamodb" \
    --query 'VpcEndpoints[0].VpcEndpointId' \
    --region $REGION \
    --output text)

if [ "$EXISTING_ENDPOINT" != "None" ] && [ -n "$EXISTING_ENDPOINT" ]; then
    echo "✅ DynamoDB VPC endpoint already exists: $EXISTING_ENDPOINT"
    echo ""
    echo "Verifying endpoint status..."
    aws ec2 describe-vpc-endpoints \
        --vpc-endpoint-ids $EXISTING_ENDPOINT \
        --query 'VpcEndpoints[0].{Id:VpcEndpointId,Service:ServiceName,State:State}' \
        --region $REGION \
        --output table
    echo ""
    echo "✅ Setup complete! DynamoDB endpoint is ready."
    exit 0
fi

# Step 4: Create VPC endpoint
echo "Step 4: Creating DynamoDB VPC endpoint..."
ENDPOINT_RESULT=$(aws ec2 create-vpc-endpoint \
    --vpc-id $VPC_ID \
    --service-name com.amazonaws.$REGION.dynamodb \
    --route-table-ids $ROUTE_TABLES \
    --region $REGION \
    --output json)

ENDPOINT_ID=$(echo $ENDPOINT_RESULT | jq -r '.VpcEndpoint.VpcEndpointId')
echo "✅ Created VPC endpoint: $ENDPOINT_ID"
echo ""

# Step 5: Verify endpoint
echo "Step 5: Verifying endpoint..."
sleep 2  # Wait for endpoint to be available
aws ec2 describe-vpc-endpoints \
    --vpc-endpoint-ids $ENDPOINT_ID \
    --query 'VpcEndpoints[0].{Id:VpcEndpointId,Service:ServiceName,State:State}' \
    --region $REGION \
    --output table

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Test your Lambda function:"
echo "   aws lambda invoke --function-name $FUNCTION_NAME --payload '{\"body\": \"{\\\"query\\\": \\\"Show me recent images\\\"}\"}' response.json"
echo ""
echo "2. Check CloudWatch logs:"
echo "   aws logs tail /aws/lambda/$FUNCTION_NAME --follow"
echo ""
echo "3. Look for: 'Created conversation ... for user ...'"
