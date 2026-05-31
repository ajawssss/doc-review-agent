"""
AgentCore-compatible HTTP server for the Jordan Blake AWS Marketing Review Agent.

Endpoints:
  GET  /          — serves the frontend UI
  GET  /ping      — health check (AgentCore requires this)
  POST /review    — review document from text (JSON body)
  POST /upload    — review document from uploaded file (multipart)
  POST /invocations — AgentCore-compatible raw prompt endpoint
"""

import json
import logging
import os
import shutil
import tempfile
from typing import AsyncGenerator

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from src.agent import build_agent
from src.tools import analyze_marketing_content, score_document

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jordan-blake-agent")

app = FastAPI(
    title="Jordan Blake AWS Marketing Review Agent",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

_agent = None


def get_agent():
    global _agent
    if _agent is None:
        logger.info("Initializing Jordan Blake agent…")
        _agent = build_agent()
        logger.info("Agent ready.")
    return _agent


def _run_tools(document_text: str) -> tuple[dict, dict]:
    """Call the scoring tools directly and return parsed dicts."""
    try:
        analysis = json.loads(analyze_marketing_content(document_text))
    except Exception:
        analysis = {}
    try:
        score = json.loads(score_document(document_text))
    except Exception:
        score = {}
    return analysis, score


def _build_review_prompt(document_text: str, title: str) -> str:
    return (
        f"I am submitting a document titled '{title}' for your review.\n\n"
        f"Document:\n{'='*60}\n{document_text}\n{'='*60}\n\n"
        "Use your analyze_marketing_content and score_document tools on this text, "
        "then deliver your full Jordan Blake marketing review."
    )


def _extract_text_from_file(tmp_path: str) -> str:
    """Extract plain text from the temp file (mirrors read_document logic)."""
    ext = os.path.splitext(tmp_path)[1].lower()

    if ext in (".txt", ".md", ".rst"):
        with open(tmp_path, "r", encoding="utf-8") as f:
            return f.read()

    if ext == ".pdf":
        import PyPDF2
        with open(tmp_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            pages = [p.extract_text() for p in reader.pages]
            return "\n\n".join(p for p in pages if p)

    if ext == ".docx":
        from docx import Document
        doc = Document(tmp_path)
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())

    raise ValueError(f"Unsupported file type: {ext}")


# ── Health check ────────────────────────────────────────────────────────────

@app.get("/ping")
async def ping():
    return JSONResponse({"status": "healthy", "agent": "Jordan Blake"})


# ── Frontend ────────────────────────────────────────────────────────────────

@app.get("/")
async def serve_frontend():
    index = os.path.join(STATIC_DIR, "index.html")
    if not os.path.isfile(index):
        return JSONResponse({"error": "Frontend not found. Run from project root."}, status_code=404)
    return FileResponse(index)


# ── Text review ────────────────────────────────────────────────────────────

@app.post("/review")
async def review_text(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Request body must be valid JSON.")

    document_text: str = body.get("documentText", "").strip()
    document_title: str = body.get("documentTitle", "Untitled Document")

    if not document_text:
        raise HTTPException(400, "'documentText' is required.")

    logger.info(f"[/review] title={document_title!r} len={len(document_text)}")

    analysis, score = _run_tools(document_text)

    agent = get_agent()
    result = agent(_build_review_prompt(document_text, document_title))

    return JSONResponse({
        "analysis": analysis,
        "score": score,
        "review": str(result),
        "agent": "Jordan Blake",
    })


# ── File upload review ──────────────────────────────────────────────────────

@app.post("/upload")
async def review_file(
    file: UploadFile = File(...),
    title: str = Form(""),
):
    allowed = {".txt", ".md", ".rst", ".pdf", ".docx"}
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(allowed))}")

    doc_title = title or file.filename or "Uploaded Document"
    logger.info(f"[/upload] file={file.filename!r} title={doc_title!r}")

    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        document_text = _extract_text_from_file(tmp_path)
    except Exception as e:
        os.unlink(tmp_path)
        raise HTTPException(422, f"Could not read file: {e}")
    finally:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass

    if not document_text.strip():
        raise HTTPException(422, "File appears to be empty or could not be parsed.")

    analysis, score = _run_tools(document_text)

    agent = get_agent()
    result = agent(_build_review_prompt(document_text, doc_title))

    return JSONResponse({
        "analysis": analysis,
        "score": score,
        "review": str(result),
        "agent": "Jordan Blake",
    })


# ── AgentCore /invocations (raw prompt) ────────────────────────────────────

@app.post("/invocations")
async def invoke(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Request body must be valid JSON.")

    prompt: str        = body.get("prompt") or body.get("inputText") or ""
    session_id: str    = body.get("sessionId", "default")
    stream: bool       = body.get("stream", False)
    document_text: str = body.get("documentText", "")
    document_title: str = body.get("documentTitle", "Untitled Document")

    if not prompt and not document_text:
        raise HTTPException(400, "Provide 'prompt' or 'documentText'.")

    if document_text and not prompt:
        prompt = _build_review_prompt(document_text, document_title)

    agent = get_agent()
    logger.info(f"[/invocations session={session_id}] stream={stream} len={len(prompt)}")

    if stream:
        return StreamingResponse(
            _stream_response(agent, prompt, session_id),
            media_type="text/event-stream",
        )

    result = agent(prompt)
    return JSONResponse({"sessionId": session_id, "response": str(result), "agent": "Jordan Blake"})


async def _stream_response(agent, prompt: str, session_id: str) -> AsyncGenerator[str, None]:
    try:
        async for chunk in agent.stream_async(prompt):
            if hasattr(chunk, "data") and chunk.data:
                yield f"data: {json.dumps({'sessionId': session_id, 'chunk': chunk.data})}\n\n"
            elif isinstance(chunk, str) and chunk:
                yield f"data: {json.dumps({'sessionId': session_id, 'chunk': chunk})}\n\n"
    except Exception as e:
        logger.error(f"[session={session_id}] Streaming error: {e}")
        yield f"data: {json.dumps({'error': str(e), 'sessionId': session_id})}\n\n"
    finally:
        yield "data: [DONE]\n\n"


# ── Local dev entry point ───────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.server:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8080)),
        reload=os.environ.get("ENV", "prod") == "dev",
        log_level="info",
    )
