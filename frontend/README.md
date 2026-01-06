---
title: CG Production Assistant - Blender Studio Assets
emoji: 🔥
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: 6.2.0
app_file: app.py
pinned: false
license: mit
short_description: Assistant for asking questions about Blender Studio's assets
---

# CG Production Assistant

An AI-powered assistant for querying metadata from Blender Studio's short films. Ask questions about assets, search by image, and explore the production database.

This space is not affiliated with Blender Studio. All assets are created by Blender Studio and available under the Creative Commons Attribution 4.0 International license.

## Development

Built as part of a CG Production Assistant system. See the [full repository](https://github.com/YOUR_USERNAME/CG_Production_LLM_Assistant) for:
- Metadata extraction pipeline
- Database schema
- Backend deployment guides
- Local development setup

## Features

- 💬 **Natural Language Queries**: Ask questions in plain English about the database
- 🖼️ **Image Search**: Upload images to find visually similar assets
- 🔍 **SQL Transparency**: See the generated SQL queries and results
- 💾 **Conversation History**: Save and resume conversations
- 🔐 **Demo Mode**: Auto-login with demo account, or create your own

## Demo Account

By default, the app uses a demo account for quick access. If you want to be able to save and resume conversations, you can create your own account:
1. Expand the "Login / Signup Options" section
2. Create your own account
3. Login with your credentials

## Tech Stack

- **Frontend**: Gradio
- **Backend**: AWS Lambda + PostgreSQL + pgvector
- **LLM**: AWS Bedrock (Llama 3.3 70B)
- **Database**: PostgreSQL with pgvector for embeddings

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
