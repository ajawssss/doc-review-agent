# -----------------------------------------------------------------------------
# What's in this file:
#   A FastAPI HTTP server that wraps the Nathan Webb agent and exposes it
#   through the two endpoints Amazon Bedrock AgentCore requires:
#     GET  /ping         — health check (AgentCore polls this before routing)
#     POST /invocations  — main entry point; accepts a document or free-form
#                          prompt and returns Nathan's review
#   Supports both blocking JSON responses and streaming via Server-Sent Events.
#
# Technologies used:
#   - FastAPI — async HTTP framework
#   - Uvicorn — ASGI server (started via CMD in Dockerfile)
#   - Strands Agents SDK — agent invocation and streaming
#   - Amazon Bedrock AgentCore — managed container runtime that calls /ping
#     and /invocations once the image is deployed
#   - Python stdlib: json, logging, os
#
# Example of what this file does:
#   AgentCore POSTs {"documentText": "Our Q3 plan...", "stream": true} to
#   /invocations. The server builds the Nathan Webb prompt, calls the agent,
#   and streams back Server-Sent Events:
#     data: {"sessionId": "abc", "chunk": "This memo has seven vague words..."}
#     data: {"sessionId": "abc", "chunk": " Verdict: Send it back."}
#     data: [DONE]
# -----------------------------------------------------------------------------
"""
AgentCore-compatible HTTP server for the Nathan Webb Doc Review Agent.

Amazon Bedrock AgentCore expects:
  POST /invocations
    Body: { "prompt": "...", "sessionId": "...", ... }
  GET  /ping
    Returns 200 to signal the container is healthy.

Streaming is supported via Server-Sent Events (text/event-stream).
"""

import json
import logging
import os
from typing import AsyncGenerator

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse

from src.agent import build_agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nathan-webb-agent")

app = FastAPI(
    title="Nathan Webb Document Review Agent",
    description="A rigorous document reviewer powered by the Nathan Webb persona.",
    version="1.0.0",
)

# Cache one agent instance per worker process (thread-safe for read-only tool use)
_agent = None


def get_agent():
    global _agent
    if _agent is None:
        logger.info("Initializing Nathan Webb agent...")
        _agent = build_agent()
        logger.info("Agent ready.")
    return _agent


# ---------------------------------------------------------------------------
# Health check — AgentCore pings this before routing traffic
# ---------------------------------------------------------------------------

@app.get("/ping")
async def ping():
    return JSONResponse(content={"status": "healthy", "agent": "Nathan Webb"})


# ---------------------------------------------------------------------------
# Main invocation endpoint
# ---------------------------------------------------------------------------

@app.post("/invocations")
async def invoke(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Request body must be valid JSON.")

    prompt: str = body.get("prompt") or body.get("inputText") or ""
    session_id: str = body.get("sessionId", "default")
    stream: bool = body.get("stream", False)
    document_text: str = body.get("documentText", "")
    document_title: str = body.get("documentTitle", "Untitled Document")

    if not prompt and not document_text:
        raise HTTPException(status_code=400, detail="Provide 'prompt' or 'documentText' in the request body.")

    # If the caller sent raw document text, wrap it in Nathan's review prompt
    if document_text and not prompt:
        prompt = (
            f"I am submitting a document titled '{document_title}' for your review.\n\n"
            f"Here is the full document text:\n\n"
            f"{'='*60}\n"
            f"{document_text}\n"
            f"{'='*60}\n\n"
            "Use your analyze_document_structure and check_customer_obsession tools on this text, "
            "then deliver your full Nathan Webb document review."
        )

    agent = get_agent()
    logger.info(f"[session={session_id}] Invoking Nathan Webb. Stream={stream}. Prompt length={len(prompt)}")

    if stream:
        return StreamingResponse(
            _stream_response(agent, prompt, session_id),
            media_type="text/event-stream",
        )

    # Non-streaming: collect and return
    result = agent(prompt)
    response_text = str(result)

    return JSONResponse(content={
        "sessionId": session_id,
        "response": response_text,
        "agent": "Nathan Webb",
    })


async def _stream_response(agent, prompt: str, session_id: str) -> AsyncGenerator[str, None]:
    """Yield Server-Sent Events from the agent's streamed output."""
    try:
        # Strands agents support async iteration when streaming=True on the model
        async for chunk in agent.stream_async(prompt):
            if hasattr(chunk, "data") and chunk.data:
                payload = json.dumps({"sessionId": session_id, "chunk": chunk.data})
                yield f"data: {payload}\n\n"
            elif isinstance(chunk, str) and chunk:
                payload = json.dumps({"sessionId": session_id, "chunk": chunk})
                yield f"data: {payload}\n\n"
    except Exception as e:
        logger.error(f"[session={session_id}] Streaming error: {e}")
        error_payload = json.dumps({"error": str(e), "sessionId": session_id})
        yield f"data: {error_payload}\n\n"
    finally:
        yield "data: [DONE]\n\n"


# ---------------------------------------------------------------------------
# Entry point for local development
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.server:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8080)),
        reload=os.environ.get("ENV", "prod") == "dev",
        log_level="info",
    )
