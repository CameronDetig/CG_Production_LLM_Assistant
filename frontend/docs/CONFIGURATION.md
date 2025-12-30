# Frontend Configuration Guide

## Environment Variables

Create a `.env` file in the `frontend/` directory:

```bash
# API Configuration
API_ENDPOINT=https://your-api-gateway-url.amazonaws.com/prod

# Cognito Configuration
COGNITO_CLIENT_ID=your-cognito-client-id
COGNITO_REGION=us-east-1
```

---

## Running Locally

### 1. Install Dependencies

```bash
cd frontend
pip install -r requirements.txt
```

### 2. Configure Environment

Update `.env` with your API Gateway URL and Cognito Client ID.

### 3. Run Gradio App

```bash
python app.py
```

The app will be available at `http://localhost:7860`

---

## Features

### Authentication

- **Demo Login**: Click "🎭 Demo Login" for instant access
  - Email: `demo@cgassistant.com`
  - Password: `DemoPass10!`
- **Custom Login**: Enter your own Cognito credentials
- **Logout**: Clear session and start fresh

### Conversation Management

- **New Conversation**: Start a fresh conversation
- **Conversation List**: View all your past conversations
- **Load Conversation**: Click to load previous chat history
- **Delete Conversation**: Remove unwanted conversations

### Chat Features

- **Text Queries**: Ask natural language questions about your assets
- **Image Upload**: Upload an image to find visually similar assets
  - Images are automatically resized to 512x512 client-side
  - Supports JPEG, PNG, and other common formats
- **Streaming Responses**: See agent reasoning and tool calls in real-time
- **Thumbnail Gallery**: View thumbnails of search results

### Agent Visibility

The chat displays agent reasoning steps:
- 🔧 **Tool calls**: See which tools the agent is using
- **Tool results**: View how many results were found
- **Final answer**: Get a comprehensive response

---

## Deployment to Hugging Face Spaces

### 1. Create Space

1. Go to [Hugging Face Spaces](https://huggingface.co/spaces)
2. Click "Create new Space"
3. Choose "Gradio" as SDK
4. Name your space (e.g., `cg-production-assistant`)

### 2. Add Files

Upload:
- `app.py`
- `requirements.txt`
- `README.md` (optional)

### 3. Configure Secrets

In Space settings, add secrets:
- `API_ENDPOINT`: Your API Gateway URL
- `COGNITO_CLIENT_ID`: Your Cognito Client ID
- `COGNITO_REGION`: `us-east-1`

### 4. Deploy

The space will automatically build and deploy.

---

## Troubleshooting

### "Authentication required" error

**Solution**: Make sure you're logged in. Click "🎭 Demo Login" or enter credentials.

### Conversations not loading

**Solution**: 
1. Check that `API_ENDPOINT` is correct
2. Verify you're logged in
3. Click "🔄 Refresh" to reload conversations

### Image upload not working

**Solution**:
1. Ensure image is in a supported format (JPEG, PNG)
2. Check that image file size is reasonable (<10MB)
3. Verify API Gateway payload size limit is set to 10MB

### Thumbnails not displaying

**Solution**:
1. Check S3 bucket permissions
2. Verify presigned URLs are being generated
3. Check browser console for CORS errors

### SSE stream timeout

**Solution**:
1. Increase timeout in `app.py` (currently 120s)
2. Check Lambda timeout settings (should be 5 minutes)
3. Verify API Gateway timeout (max 29 seconds for REST, use WebSocket for longer)

---

## UI Customization

### Change Theme

Edit `app.py`:

```python
demo = gr.Blocks(theme=gr.themes.Monochrome())  # or Soft(), Glass(), etc.
```

### Adjust Layout

Modify column scales:

```python
with gr.Row():
    with gr.Column(scale=1):  # Sidebar
        # ...
    with gr.Column(scale=3):  # Main area (3x wider)
        # ...
```

### Customize Colors

Use custom theme:

```python
theme = gr.themes.Soft(
    primary_hue="blue",
    secondary_hue="gray",
    neutral_hue="slate"
)

demo = gr.Blocks(theme=theme)
```

---

## Performance Tips

### Reduce Cold Starts

- Keep a browser tab open to maintain connection
- Consider using Hugging Face Spaces persistent storage

### Optimize Image Upload

- Images are resized to 512x512 client-side
- Use JPEG format for smaller file sizes
- Compress images before upload if very large

### Conversation Loading

- Conversations are loaded on demand
- Only last 10 messages are sent as context to agent
- Delete old conversations to improve performance

---

## Security Notes

### Demo Account

- Demo account is public and read-only
- Do not store sensitive information in demo conversations
- Consider rate limiting for demo account in production

### Authentication Tokens

- Tokens are stored in memory (not persisted)
- Tokens expire after 1 hour (refresh not implemented yet)
- Re-login if you get 401 errors

### CORS

- API must allow requests from Hugging Face Spaces domain
- Update API Gateway CORS settings if deploying to custom domain

---

## Next Steps

### Future Enhancements

1. **Token Refresh**: Automatically refresh expired tokens
2. **Conversation Titles**: Allow users to edit conversation titles
3. **Export Conversations**: Download chat history as JSON/PDF
4. **Advanced Filters**: Filter conversations by date, topic, etc.
5. **Dark Mode**: Add theme toggle
6. **File Upload**: Support uploading multiple images
7. **Voice Input**: Add speech-to-text for queries

### Integration Ideas

1. **Slack Bot**: Integrate with Slack for team access
2. **API Client**: Create Python SDK for programmatic access
3. **Mobile App**: Build React Native mobile app
4. **Browser Extension**: Chrome extension for quick access

---

## Support

For issues or questions:
1. Check CloudWatch logs for backend errors
2. Check browser console for frontend errors
3. Verify all environment variables are set correctly
4. Test API endpoints directly with curl/Postman
