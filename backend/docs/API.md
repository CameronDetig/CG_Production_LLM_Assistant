# API Documentation

## Overview

The CG Production LLM Assistant API provides endpoints for AI-powered search and conversation management for CG production assets.

**Base URL**: `https://your-api-gateway-url.amazonaws.com/prod`

**Authentication**: Bearer token (Cognito JWT) in `Authorization` header

---

## Endpoints

### 1. POST /chat

Main chat endpoint with LangGraph ReAct agent.

**Request:**
```json
{
  "query": "Show me 4K renders",
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",  // Optional, omit for new conversation
  "uploaded_image_base64": "base64-encoded-image"  // Optional, for image search
}
```

**Headers:**
```
Authorization: Bearer <cognito-jwt-token>
Content-Type: application/json
```

**Response:** Server-Sent Events (SSE) stream

**Event Types:**

| Event | Data | Description |
|-------|------|-------------|
| `agent_start` | `{conversation_id, iterations}` | Agent started processing |
| `tool_call` | `{tool, args}` | Agent calling a tool |
| `tool_result` | `{tool, count, results}` | Tool execution result |
| `thumbnail` | `{file_id, file_name, thumbnail_url}` | Thumbnail for a result |
| `answer_start` | `{}` | Starting final answer generation |
| `answer_chunk` | `{text}` | Chunk of final answer |
| `answer_end` | `{}` | Final answer complete |
| `done` | `{conversation_id, message_count}` | Request complete |

**Example Response Stream:**
```
event: agent_start
data: {"conversation_id": "550e8400-...", "iterations": 2}

event: tool_call
data: {"tool": "filter_by_metadata", "args": {"min_resolution_x": 3840, "min_resolution_y": 2160}}

event: tool_result
data: {"tool": "filter_by_metadata", "count": 5, "results": [...]}

event: thumbnail
data: {"file_id": 123, "file_name": "render_001.png", "thumbnail_url": "https://..."}

event: answer_start
data: {}

event: answer_chunk
data: {"text": "I found 5 4K renders..."}

event: answer_end
data: {}

event: done
data: {"conversation_id": "550e8400-...", "message_count": 4}
```

---

### 2. GET /conversations

List all conversations for the authenticated user.

**Headers:**
```
Authorization: Bearer <cognito-jwt-token>
```

**Response:**
```json
{
  "conversations": [
    {
      "conversation_id": "550e8400-...",
      "user_id": "demo@cgassistant.com",
      "title": "4K Renders Search",
      "created_at": "2025-12-30T14:00:00Z",
      "updated_at": "2025-12-30T14:05:30Z",
      "message_count": 4
    }
  ]
}
```

---

### 3. GET /conversations/{id}

Get a specific conversation with full message history.

**Headers:**
```
Authorization: Bearer <cognito-jwt-token>
```

**Response:**
```json
{
  "conversation": {
    "conversation_id": "550e8400-...",
    "user_id": "demo@cgassistant.com",
    "title": "4K Renders Search",
    "created_at": "2025-12-30T14:00:00Z",
    "updated_at": "2025-12-30T14:05:30Z",
    "message_count": 4,
    "messages": [
      {
        "role": "user",
        "content": "Show me 4K renders",
        "timestamp": "2025-12-30T14:00:00Z"
      },
      {
        "role": "assistant",
        "content": "I found 5 4K renders...",
        "timestamp": "2025-12-30T14:00:05Z",
        "tool_calls": [
          {
            "tool": "filter_by_metadata",
            "args": {"min_resolution_x": 3840, "min_resolution_y": 2160},
            "result": [...]
          }
        ]
      }
    ]
  }
}
```

---

### 4. DELETE /conversations/{id}

Delete a conversation.

**Headers:**
```
Authorization: Bearer <cognito-jwt-token>
```

**Response:**
```json
{
  "message": "Conversation deleted"
}
```

---

## Authentication

### Login (Demo Account)

Use AWS Cognito SDK to authenticate:

```javascript
import { CognitoIdentityProviderClient, InitiateAuthCommand } from "@aws-sdk/client-cognito-identity-provider";

const client = new CognitoIdentityProviderClient({ region: "us-east-1" });

const command = new InitiateAuthCommand({
  ClientId: "YOUR_CLIENT_ID",
  AuthFlow: "USER_PASSWORD_AUTH",
  AuthParameters: {
    USERNAME: "demo@cgassistant.com",
    PASSWORD: "DemoPass10!"
  }
});

const response = await client.send(command);
const idToken = response.AuthenticationResult.IdToken;
```

**Demo Account:**
- Email: `demo@cgassistant.com`
- Password: `DemoPass10!`

---

## Error Responses

**400 Bad Request:**
```json
{
  "error": "Query is required"
}
```

**401 Unauthorized:**
```json
{
  "error": "Authentication required"
}
```

**404 Not Found:**
```json
{
  "error": "Conversation not found"
}
```

**500 Internal Server Error:**
```json
{
  "error": "Internal server error"
}
```

---

## Rate Limiting

No rate limiting currently implemented. Consider adding for production:
- Demo account: 100 requests/hour
- Authenticated users: 1000 requests/hour

---

## CORS

All endpoints support CORS with:
- `Access-Control-Allow-Origin: *`
- `Access-Control-Allow-Headers: Content-Type,Authorization`
- `Access-Control-Allow-Methods: GET,POST,DELETE,OPTIONS`

---

## Agent Tools

The agent has access to the following tools:

1. **search_by_metadata_embedding** - Semantic text search on file metadata
2. **search_by_visual_embedding** - CLIP-based visual search from text description
3. **search_by_uploaded_image** - CLIP-based visual search from uploaded image
4. **keyword_search_tool** - Traditional keyword search
5. **analytics_query** - Database statistics and counts
6. **filter_by_metadata** - Filter by file type, resolution, extension
7. **get_file_details** - Get detailed info about a specific file

The agent automatically selects appropriate tools based on the user's query.

---

## Example Usage

### Python Client

```python
import requests
import json

# Authenticate
auth_response = requests.post(
    "https://cognito-idp.us-east-1.amazonaws.com/",
    headers={"X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth"},
    json={
        "ClientId": "YOUR_CLIENT_ID",
        "AuthFlow": "USER_PASSWORD_AUTH",
        "AuthParameters": {
            "USERNAME": "demo@cgassistant.com",
            "PASSWORD": "DemoPass10!"
        }
    }
)
id_token = auth_response.json()["AuthenticationResult"]["IdToken"]

# Chat
response = requests.post(
    "https://your-api-gateway-url.amazonaws.com/prod/chat",
    headers={
        "Authorization": f"Bearer {id_token}",
        "Content-Type": "application/json"
    },
    json={"query": "Show me 4K renders"},
    stream=True
)

# Parse SSE stream
for line in response.iter_lines():
    if line:
        line = line.decode('utf-8')
        if line.startswith('event:'):
            event_type = line.split(':', 1)[1].strip()
        elif line.startswith('data:'):
            data = json.loads(line.split(':', 1)[1].strip())
            print(f"{event_type}: {data}")
```

### JavaScript Client

```javascript
const response = await fetch('https://your-api-gateway-url.amazonaws.com/prod/chat', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${idToken}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ query: 'Show me 4K renders' })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  
  const chunk = decoder.decode(value);
  const lines = chunk.split('\n');
  
  for (const line of lines) {
    if (line.startsWith('event:')) {
      const eventType = line.substring(7);
    } else if (line.startsWith('data:')) {
      const data = JSON.parse(line.substring(6));
      console.log(eventType, data);
    }
  }
}
```

---

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for deployment instructions.
