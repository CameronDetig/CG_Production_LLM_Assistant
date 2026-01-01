# Hugging Face Spaces Deployment Guide

## Overview

This guide walks you through deploying the CG Production LLM Assistant frontend to Hugging Face Spaces.

## Prerequisites

- Hugging Face account
- AWS Lambda backend deployed and running
- API Gateway endpoint URL
- Cognito demo account credentials

## Step 1: Create a New Space

1. Go to [Hugging Face Spaces](https://huggingface.co/spaces)
2. Click "Create new Space"
3. Configure:
   - **Owner**: Your username or organization
   - **Space name**: `cg-production-assistant` (or your preferred name)
   - **License**: Apache 2.0 (or your choice)
   - **SDK**: Gradio
   - **Visibility**: Public or Private

## Step 2: Clone the Space Repository

```bash
git clone https://huggingface.co/spaces/YOUR_USERNAME/cg-production-assistant
cd cg-production-assistant
```

## Step 3: Copy Frontend Files

```bash
# Copy app.py and requirements.txt
cp ../frontend/app.py .
cp ../frontend/requirements.txt .
```

## Step 4: Create README.md

Create a `README.md` file for your Space:

```markdown
---
title: CG Production Assistant
emoji: 🎬
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: 4.0.0
app_file: app.py
pinned: false
---

# CG Production LLM Assistant

AI-powered search for CG production assets with conversation memory.

## Features

- 🔍 Semantic search across Blender files, images, and videos
- 🖼️ Visual search with image upload
- 💬 Conversation history and management
- 🔐 User authentication with demo account

## Usage

1. The app auto-logs in with a demo account
2. Ask questions about your CG assets
3. Upload images for visual similarity search
4. Optionally create your own account for private conversations

## Tech Stack

- **Frontend**: Gradio (Hugging Face Spaces)
- **Backend**: AWS Lambda + API Gateway
- **Database**: PostgreSQL (AWS RDS)
- **AI Models**: AWS Bedrock (Llama 3.2)
- **Authentication**: AWS Cognito
```

## Step 5: Configure Secrets

In your Space settings, add the following secrets:

1. Go to **Settings** > **Repository secrets**
2. Add these secrets:

| Secret Name | Value | Description |
|------------|-------|-------------|
| `API_ENDPOINT` | `https://your-api-id.execute-api.us-east-1.amazonaws.com/prod` | Your AWS API Gateway endpoint |
| `DEMO_EMAIL` | `demo@cgassistant.com` | Demo account email |
| `DEMO_PASSWORD` | `DemoPass10!` | Demo account password |

> **Important**: Do NOT include `/chat` in the API_ENDPOINT - it will be appended automatically

## Step 6: Push to Hugging Face

```bash
git add .
git commit -m "Initial deployment"
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
cd frontend

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
