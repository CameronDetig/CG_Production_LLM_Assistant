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

- 🔍 **Semantic Search**: Find files using natural language descriptions
- 🖼️ **Visual Search**: Upload images to find visually similar assets
- 💬 **Conversation History**: Persistent chat history across sessions
- 🔐 **Authentication**: Auto-login with demo account or create your own
- 🎨 **Asset Types**: Search across Blender files, images, and videos
- 📊 **Database Stats**: Query file counts and metadata

## Usage

1. **Auto-Login**: The app automatically logs in with a demo account
2. **Ask Questions**: "Show me 4K renders" or "Find character models"
3. **Visual Search**: Upload an image to find similar assets
4. **Manage Conversations**: View history, create new chats, delete old ones
5. **Optional Login**: Expand "Login Options" to use your own account

## Example Queries

- "How many files are in the database?"
- "Show me all Blender files with Cycles render engine"
- "Find images of red cars"
- "What 4K renders do we have?"
- "Show me files modified in the last week"

## Tech Stack

- **Frontend**: Gradio (Hugging Face Spaces)
- **Backend**: AWS Lambda + API Gateway
- **Database**: PostgreSQL (AWS RDS) with pgvector
- **AI Models**: AWS Bedrock (Llama 3.2)
- **Embeddings**: Sentence Transformers + CLIP
- **Authentication**: AWS Cognito
- **Storage**: AWS S3 (thumbnails)

## Architecture

```
┌─────────────────────┐
│  Hugging Face Space │
│   (Gradio Frontend) │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   AWS API Gateway   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│    AWS Lambda       │
│  (LangGraph Agent)  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  PostgreSQL + RDS   │
│   (Vector Search)   │
└─────────────────────┘
```

## Demo Account

The app uses a shared demo account for quick access. For private conversations, you can:
1. Expand the "Login Options" section
2. Create your own Cognito account
3. Login with your credentials

## Development

Built as part of a CG production metadata extraction and search system. See the [full repository](https://github.com/YOUR_USERNAME/CG_Production_LLM_Assistant) for:
- Metadata extraction pipeline
- Database schema
- Backend deployment guides
- Local development setup

## License

Apache 2.0
