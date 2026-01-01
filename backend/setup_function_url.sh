#!/bin/bash

# Setup Lambda Function URL
# This creates a public HTTPS endpoint for your Lambda function

set -e

FUNCTION_NAME="cg-production-chatbot"
REGION="us-east-1"

echo "=========================================="
echo "Setting up Lambda Function URL"
echo "=========================================="
echo ""

# Create Function URL
echo "Creating Function URL..."
URL_CONFIG=$(aws lambda create-function-url-config \
    --function-name $FUNCTION_NAME \
    --auth-type NONE \
    --cors "AllowOrigins=*,AllowMethods=*,AllowHeaders=*,MaxAge=86400" \
    --region $REGION \
    --output json 2>/dev/null || echo "exists")

if [ "$URL_CONFIG" = "exists" ]; then
    echo "Function URL already exists, fetching..."
    URL_CONFIG=$(aws lambda get-function-url-config \
        --function-name $FUNCTION_NAME \
        --region $REGION \
        --output json)
fi

# Extract the URL
FUNCTION_URL=$(echo $URL_CONFIG | grep -o '"FunctionUrl": "[^"]*' | cut -d'"' -f4)

echo ""
echo "✅ Lambda Function URL created!"
echo ""
echo "=========================================="
echo "Your API Endpoint:"
echo "$FUNCTION_URL"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Copy the URL above"
echo "2. Set it in your frontend .env file:"
echo "   API_ENDPOINT=$FUNCTION_URL"
echo ""
echo "3. Or set as environment variable:"
echo "   export API_ENDPOINT=\"$FUNCTION_URL\""
echo ""

# Add public invoke permission
echo "Adding public invoke permission..."
aws lambda add-permission \
    --function-name $FUNCTION_NAME \
    --statement-id FunctionURLAllowPublicAccess \
    --action lambda:InvokeFunctionUrl \
    --principal "*" \
    --function-url-auth-type NONE \
    --region $REGION \
    --output text 2>/dev/null || echo "Permission already exists"

echo ""
echo "✅ Setup complete!"
