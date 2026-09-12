"""ASGI transport for the CG Production Assistant.

The AWS Lambda Web Adapter runs this app in Lambda.  Keeping HTTP concerns here
lets the agent and service modules remain usable from diagnostics and tests.
"""

import asyncio
import logging
import os
from typing import Any, AsyncGenerator, Dict, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.auth.cognito import authenticate_user, extract_user_from_token, signup_user
from src.core.chat_agent import run_chat_agent
from src.services.bedrock_client import invoke_bedrock
from src.services.conversations import (
    add_message,
    create_conversation,
    delete_conversation,
    generate_title_from_query,
    get_conversation,
    get_conversation_context,
    list_conversations,
)
from src.services.streaming import dynamo_safe, final_answer_prompt, sse

logger = logging.getLogger(__name__)
app = FastAPI(title="CG Production Assistant API", docs_url=None, redoc_url=None)


class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=20_000)
    conversation_id: Optional[str] = None
    uploaded_image_base64: Optional[str] = Field(default=None, max_length=2_000_000)


class CredentialsRequest(BaseModel):
    email: str
    password: str


def authenticated_user(
    x_cognito_token: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
) -> str:
    """Accept the CloudFront-forwarded token or a local Bearer token."""
    token = x_cognito_token
    if not token and authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer":
            token = value
    user_id = extract_user_from_token(token) if token else None
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user_id


async def chat_events(
    request: Request,
    payload: ChatRequest,
    user_id: str,
) -> AsyncGenerator[str, None]:
    conversation_id = payload.conversation_id
    history = []
    if conversation_id:
        conversation = await asyncio.to_thread(get_conversation, conversation_id, user_id)
        if conversation:
            history = await asyncio.to_thread(
                get_conversation_context, conversation_id, user_id, 10
            )
        else:
            conversation_id = None

    if not conversation_id:
        title = generate_title_from_query(payload.query)
        conversation_id = await asyncio.to_thread(create_conversation, user_id, title)

    await asyncio.to_thread(add_message, conversation_id, user_id, "user", payload.query)
    yield sse("agent_start", {"conversation_id": conversation_id, "attempts": 0})
    yield sse("status", {"stage": "analyzing", "message": "Analyzing your request"})

    task = asyncio.create_task(
        asyncio.to_thread(
            run_chat_agent,
            payload.query,
            history,
            payload.uploaded_image_base64,
            2,
        )
    )
    try:
        while not task.done():
            if await request.is_disconnected():
                task.cancel()
                return
            done, _ = await asyncio.wait({task}, timeout=12)
            if not done:
                # SSE comments keep CloudFront and browsers from treating a long model or
                # database operation as an idle response.
                yield ": heartbeat\n\n"

        result = await task
        if result.get("enhanced_query"):
            yield sse("enhanced_query", {"query": result["enhanced_query"]})

        all_queries = result.get("all_sql_queries", [])
        for query_info in all_queries:
            attempt = query_info.get("attempt", 1)
            yield sse("sql_query", {"query": query_info["sql"], "attempt": attempt})
            if query_info.get("results") is not None:
                yield sse(
                    "query_results",
                    {
                        "count": query_info.get("result_count", 0),
                        "attempt": attempt,
                        "results": query_info["results"][:5],
                    },
                )
            if query_info.get("feedback"):
                yield sse(
                    "retry_feedback",
                    {"feedback": query_info["feedback"], "attempt": attempt},
                )

        if not all_queries and result.get("sql_query"):
            yield sse("sql_query", {"query": result["sql_query"], "attempt": 1})
            query_results = result.get("query_results", [])
            if query_results:
                yield sse(
                    "query_results",
                    {"count": len(query_results), "attempt": 1, "results": query_results[:5]},
                )

        for thumbnail in result.get("thumbnails_to_display", []):
            yield sse("thumbnail", thumbnail)

        yield sse("answer_start", {})
        candidate = result.get("final_answer") or "No answer was generated."
        chunks = invoke_bedrock(
            final_answer_prompt(payload.query, candidate),
            streaming=True,
            temperature=0.2,
            max_tokens=2048,
        )
        complete_answer = ""
        for chunk in chunks:
            if await request.is_disconnected():
                return
            complete_answer += chunk
            yield sse("answer_chunk", {"text": chunk})

        yield sse("answer_end", {})
        await asyncio.to_thread(
            add_message,
            conversation_id,
            user_id,
            "assistant",
            complete_answer,
            [
                {
                    "sql_query": result.get("sql_query"),
                    "result_count": len(result.get("query_results", [])),
                    "results": dynamo_safe(result.get("query_results", [])[:10]),
                }
            ],
        )
        yield sse(
            "done",
            {
                "conversation_id": conversation_id,
                "message_count": len(history) + 2,
            },
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.exception("Streaming chat failed")
        yield sse("error", {"message": "The assistant could not complete this request."})
        yield sse("done", {"conversation_id": conversation_id, "failed": True})


@app.get("/health")
@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/api/chat")
async def chat(
    payload: ChatRequest,
    request: Request,
    user_id: str = Depends(authenticated_user),
) -> StreamingResponse:
    return StreamingResponse(
        chat_events(request, payload, user_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@app.get("/api/conversations")
async def conversations(user_id: str = Depends(authenticated_user)) -> Dict[str, Any]:
    return {"conversations": await asyncio.to_thread(list_conversations, user_id, 50)}


@app.get("/api/conversations/{conversation_id}")
async def conversation(
    conversation_id: str, user_id: str = Depends(authenticated_user)
) -> Dict[str, Any]:
    item = await asyncio.to_thread(get_conversation, conversation_id, user_id)
    if not item:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"conversation": item}


@app.delete("/api/conversations/{conversation_id}")
async def remove_conversation(
    conversation_id: str, user_id: str = Depends(authenticated_user)
) -> Dict[str, str]:
    deleted = await asyncio.to_thread(delete_conversation, conversation_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"message": "Conversation deleted"}


# Temporary compatibility routes for the Gradio validation period.
@app.post("/api/auth")
async def auth(payload: CredentialsRequest) -> Dict[str, Any]:
    tokens = await asyncio.to_thread(authenticate_user, payload.email, payload.password)
    if not tokens:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {**tokens, "user_id": payload.email}


@app.post("/api/signup")
async def signup(payload: CredentialsRequest) -> Dict[str, Any]:
    result = await asyncio.to_thread(signup_user, payload.email, payload.password)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "Sign-up failed"))
    response: Dict[str, Any] = {
        "message": result["message"],
        "user_confirmed": result.get("user_confirmed", False),
    }
    if result.get("tokens"):
        response.update(result["tokens"])
        response["user_id"] = payload.email
    return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
