# CG Production LLM Assistant - Frontend Quick Start

This guide covers everything you need to run, configure, and deploy the CG Production Assistant frontend.

## 📋 Overview

The Frontend is a Gradio-based chat interface that connects to an AWS Lambda backend. It features:
- 💬 **Chat Interface**: Natural language queries about your assets
- 🌊 **Streaming Responses**: Real-time token streaming
- 🔍 **Visual Search**: Upload images to find similar assets
- 🔐 **Authentication**: AWS Cognito integration (Demo + Custom accounts)

## 🚀 Prerequisites

1. **Python 3.10+** installed
2. **AWS Lambda Backend** deployed (URL needed)
3. **Cognito User Pool** (optional, for custom accounts)

## 💻 Local Setup

### 1. Install Dependencies

```bash
cd frontend
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file in the `frontend/` directory (or assume defaults for testing). 

**Recommended `.env` configuration:**

```env
# Backend API Endpoint (Required for chat)
# Replace with your actual Lambda Function URL or API Gateway endpoint
API_ENDPOINT=https://fhvltd2p33ejzyk5l5tgxyz4340qrghe.lambda-url.us-east-1.on.aws

# Demo Account (Optional - defaults are built-in)
DEMO_EMAIL=demo@cgassistant.com
DEMO_PASSWORD=DemoPass10!

# Optional: AWS Configuration (only if running local backend)
AWS_REGION=us-east-1
```

### 3. Run the App

```bash
python app.py
```

Open **http://localhost:7860** in your browser.

## ✨ Features Breakdown

### Authentication
- **Demo Login**: Click "Login" on the sidebar for instant access.
- **Sign Up**: Create a new account (requires backend configuration).
- **Auto-Login**: App attempts to auto-login the demo user on load.

### Chat & Search
- **Text Queries**: "Find assets with dark lighting"
- **Image Upload**: Drag & drop an image to find visually similar assets.
- **History**: View and load past conversations from the sidebar.

## 🚢 Deployment

### Hugging Face Spaces

Use the `deploy_to_hf.sh` script to deploy to Hugging Face Spaces.

1. **Set your HF Username:**
   ```bash
   export HF_USERNAME=your-username
   ```

2. **Run Deployment Script:**
   ```bash
   ./deploy_to_hf.sh
   ```

3. **Configure Secrets:**
   Go to your Space Settings > Repository Secrets and add:
   - `API_ENDPOINT`: Your Lambda URL
   - `DEMO_EMAIL`: `demo@cgassistant.com`
   - `DEMO_PASSWORD`: `DemoPass10!`

See [HUGGINGFACE_DEPLOYMENT.md](HUGGINGFACE_DEPLOYMENT.md) for details.

## 🔧 Troubleshooting

### "Authentication required" error
- **Solution**: Ensure you are logged in. Check if `API_ENDPOINT` is correct in `.env`.

### Connection Errors
- **Solution**: Verify your Lambda function URL is active and accessible.

### Gradio Version Issues
- **Solution**: This app is optimized for Gradio 6.2.0+. Ensure `requirements.txt` is installed.
