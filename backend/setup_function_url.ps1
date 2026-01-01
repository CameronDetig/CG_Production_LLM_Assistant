# Setup Lambda Function URL (PowerShell version)
# This creates a public HTTPS endpoint for your Lambda function

$FUNCTION_NAME = "cg-production-chatbot"
$REGION = "us-east-1"

Write-Host "==========================================" -ForegroundColor Green
Write-Host "Setting up Lambda Function URL" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""

# Create Function URL
Write-Host "Creating Function URL..."
try {
    $urlConfig = aws lambda create-function-url-config `
        --function-name $FUNCTION_NAME `
        --auth-type NONE `
        --cors "AllowOrigins=*,AllowMethods=*,AllowHeaders=*,MaxAge=86400" `
        --region $REGION `
        --output json | ConvertFrom-Json
} catch {
    Write-Host "Function URL might already exist, fetching..." -ForegroundColor Yellow
    $urlConfig = aws lambda get-function-url-config `
        --function-name $FUNCTION_NAME `
        --region $REGION `
        --output json | ConvertFrom-Json
}

$FUNCTION_URL = $urlConfig.FunctionUrl

Write-Host ""
Write-Host "✅ Lambda Function URL created!" -ForegroundColor Green
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Your API Endpoint:" -ForegroundColor Cyan
Write-Host $FUNCTION_URL -ForegroundColor Yellow
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Copy the URL above"
Write-Host "2. Set it in your frontend .env file:"
Write-Host "   API_ENDPOINT=$FUNCTION_URL" -ForegroundColor Yellow
Write-Host ""
Write-Host "3. Or set as environment variable:"
Write-Host "   `$env:API_ENDPOINT=`"$FUNCTION_URL`"" -ForegroundColor Yellow
Write-Host ""

# Add public invoke permission
Write-Host "Adding public invoke permission..."
try {
    aws lambda add-permission `
        --function-name $FUNCTION_NAME `
        --statement-id FunctionURLAllowPublicAccess `
        --action lambda:InvokeFunctionUrl `
        --principal "*" `
        --function-url-auth-type NONE `
        --region $REGION `
        --output text | Out-Null
    Write-Host "✅ Permission added" -ForegroundColor Green
} catch {
    Write-Host "Permission already exists" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "✅ Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "To use this endpoint, run:" -ForegroundColor Cyan
Write-Host "`$env:API_ENDPOINT=`"$FUNCTION_URL`"" -ForegroundColor Yellow
Write-Host "python app.py" -ForegroundColor Yellow
