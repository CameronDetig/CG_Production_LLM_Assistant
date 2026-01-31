# Hugging Face Spaces Deployment Guide

## Overview

This guide walks you through deploying the CG Production LLM Assistant frontend to Hugging Face Spaces.

## Prerequisites

- Hugging Face account
- AWS Lambda backend deployed and running
- API Gateway endpoint URL
- Cognito demo account credentials

## Automated Deployment (Recommended)

The easiest way to deploy is using the included script.

### 1. Set your Hugging Face Username
```bash
export HF_USERNAME=your-username
```

### 2. Run Deployment Script
```bash
cd frontend_gradio
./deploy_to_hf.sh
```

This script will:
- Initialize the git repository
- Configure the HF remote
- Push only the necessary files (`app.py`, `requirements.txt`, `README.md`)
- Force push to ensure a clean state

### 3. Configure Secrets
After deployment, go to your Space Settings > Repository Secrets and add:
- `API_ENDPOINT`: Your Lambda URL
- `DEMO_EMAIL`: `demo@cgassistant.com`
- `DEMO_PASSWORD`: `DemoPass10!`

## Manual Deployment

If you prefer to deploy manually:

1. **Clone the Space:**
   ```bash
   git clone https://huggingface.co/spaces/YOUR_USERNAME/cg-production-assistant
   cd cg-production-assistant
   ```

2. **Copy Files:**
   ```bash
   cp ../frontend_gradio/app.py .
   cp ../frontend_gradio/requirements.txt .
   cp ../frontend_gradio/.gitignore .
   ```

3. **Create README.md:**
   Ensure it has the correct YAML frontmatter:
   ```yaml
   ---
   title: CG Production Assistant
   emoji: 🎬
   colorFrom: blue
   colorTo: purple
   sdk: gradio
   sdk_version: 6.2.0
   app_file: app.py
   pinned: false
   license: mit
   ---
   ```

4. **Push:**
   ```bash
   git add .
   git commit -m "Deploy"
   git push
   ```

## Step 7: Verify Deployment

1. Wait for the Space to build (usually 1-2 minutes)
2. Open your Space URL: `https://huggingface.co/spaces/YOUR_USERNAME/cg-production-assistant`
3. Verify:
   - ✅ Auto-login shows "Logged in as demo@cgassistant.com"
   - ✅ Can send messages and get responses
   - ✅ Streaming works correctly
   - ✅ Thumbnails display (if available)

## Troubleshooting

### Space won't build

**Error**: `ModuleNotFoundError`
- **Solution**: Check `requirements.txt` has all dependencies

**Error**: `Port already in use`
- **Solution**: Gradio automatically uses port 7860, no action needed

### Auto-login fails

**Error**: "Authentication error"
- **Solution**: Check that `API_ENDPOINT`, `DEMO_EMAIL`, and `DEMO_PASSWORD` secrets are set correctly
- **Solution**: Verify backend `/auth` endpoint is deployed and accessible

### API requests fail

**Error**: "API returned status 403" or "CORS error"
- **Solution**: Check API Gateway CORS configuration
- **Solution**: Verify Lambda function has proper permissions

**Error**: "API returned status 500"
- **Solution**: Check Lambda logs in CloudWatch
- **Solution**: Verify all environment variables are set in Lambda

### Conversations not loading

**Error**: Empty conversations list
- **Solution**: Check DynamoDB table exists and Lambda has permissions
- **Solution**: Verify user_id matches between authentication and conversation queries

## Updating the Space

To update your deployed Space:

```bash
# Make changes to app.py locally
# Test locally first
python app.py

# Push changes
git add app.py
git commit -m "Update: description of changes"
git push
```

The Space will automatically rebuild with your changes.

## Local Testing

Before deploying to HF Spaces, test locally:

```bash
cd frontend_gradio

# Set environment variables
export API_ENDPOINT="https://your-api-gateway.com/prod"
export DEMO_EMAIL="demo@cgassistant.com"
export DEMO_PASSWORD="DemoPass10!"

# Run locally
python app.py
```

Open http://localhost:7860 to test.

## Security Notes

- Demo credentials are stored as HF Spaces secrets (not in code)
- All authentication happens server-side via Lambda
- Users can create their own accounts for private conversations
- Tokens are not stored permanently (session-only)

## Support

For issues or questions:
- Check CloudWatch logs for backend errors
- Check HF Spaces logs for frontend errors
- Verify all environment variables and secrets are set correctly
