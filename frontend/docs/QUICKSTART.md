# Quick Start Guide - Testing the Frontend

## Issue

The app is trying to connect to a placeholder API endpoint. You need to configure your actual Lambda API Gateway URL.

## Solution 1: Set Environment Variable (Quick Test)

In PowerShell:
```powershell
$env:API_ENDPOINT = "https://YOUR-API-ID.execute-api.us-east-1.amazonaws.com/prod"
$env:DEMO_EMAIL = "demo@cgassistant.com"
$env:DEMO_PASSWORD = "DemoPass10!"

python app.py
```

## Solution 2: Create .env File (Recommended)

Create `frontend/.env` file:
```env
API_ENDPOINT=https://YOUR-API-ID.execute-api.us-east-1.amazonaws.com/prod
DEMO_EMAIL=demo@cgassistant.com
DEMO_PASSWORD=DemoPass10!
```

Then install python-dotenv and run:
```powershell
pip install python-dotenv
python app.py
```

## Finding Your API Gateway URL

1. Go to AWS Console > API Gateway
2. Find your API (probably named something like "cg-chatbot-api")
3. Click on "Stages" > "prod"
4. Copy the "Invoke URL" at the top

It should look like: `https://abc123xyz.execute-api.us-east-1.amazonaws.com/prod`

## Testing Without Backend (Optional)

If you want to test the UI without the backend, you can temporarily modify line 17 in `app.py`:

```python
# Comment out the real endpoint
# API_ENDPOINT = os.getenv("API_ENDPOINT", "https://your-api-gateway-url.amazonaws.com/prod")

# Use a mock endpoint for UI testing
API_ENDPOINT = "http://localhost:8000"  # Will fail gracefully
```

This will let you see the UI, but authentication and chat won't work.

## Current Status

✅ Gradio 6.0 compatibility fixed
✅ Chat format updated to message dictionaries
✅ Auto-login function fixed
❌ Need to configure API_ENDPOINT

## Next Steps

1. Find your API Gateway URL (see above)
2. Set the environment variable OR create .env file
3. Run `python app.py`
4. Open http://localhost:7860
5. Verify auto-login works
