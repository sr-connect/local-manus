"""
FastAPI server — streams agent events to the browser via Server-Sent Events.

Endpoints:
  POST /api/chat          → start a task, returns SSE stream
  GET  /api/sessions      → list active session IDs
  GET  /api/sessions/{id} → list files in a session workspace
  DELETE /api/sessions/{id} → destroy a session workspace
  GET  /workspace/{sid}/{path} → download a workspace file
  GET  /                  → serve the UI
"""
from __future__ import annotations
import asyncio
import json
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from agent.core import Agent, AgentEvent
from api.models import ChatRequest, SessionInfo
from llm.factory import create_provider
from sandbox.workspace import Workspace
from tools import get_all_tools
import config

app = FastAPI(title="LocalManus", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active sessions: session_id → Workspace
_sessions: dict[str, Workspace] = {}

UI_DIR = Path(__file__).parent.parent / "ui"


# ── UI ─────────────────────────────────────────────────────────────────────────

@app.get("/")
async def serve_ui():
    index = UI_DIR / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="UI not found")
    return FileResponse(index)


# ── Chat (SSE streaming) ────────────────────────────────────────────────────────

async def _event_stream(request: ChatRequest) -> AsyncIterator[str]:
    # Get or create workspace
    if request.session_id and request.session_id in _sessions:
        ws = _sessions[request.session_id]
    else:
        ws = Workspace(session_id=request.session_id)
        _sessions[ws.session_id] = ws

    # Send session_id first so the client knows which session this is
    yield f"data: {json.dumps({'type': 'session', 'session_id': ws.session_id})}\n\n"

    # Build LLM provider
    try:
        llm = create_provider(
            provider=request.provider,
            model=request.model,
            api_key=request.api_key,
            base_url=request.base_url,
        )
    except ValueError as exc:
        yield AgentEvent(type="error", content=str(exc), is_error=True).to_sse()
        yield AgentEvent(type="done").to_sse()
        return

    tools = get_all_tools(ws.path)
    agent = Agent(llm=llm, tools=tools, workspace=ws.path)

    async for event in agent.run(request.message):
        yield event.to_sse()
        await asyncio.sleep(0)  # yield control so SSE flushes


@app.post("/api/chat")
async def chat(request: ChatRequest):
    return StreamingResponse(
        _event_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── Session management ──────────────────────────────────────────────────────────

@app.get("/api/sessions")
async def list_sessions():
    return {"sessions": list(_sessions.keys())}


@app.get("/api/sessions/{session_id}", response_model=SessionInfo)
async def get_session(session_id: str):
    ws = _sessions.get(session_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionInfo(session_id=session_id, files=ws.list_files())


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    ws = _sessions.pop(session_id, None)
    if ws is None:
        raise HTTPException(status_code=404, detail="Session not found")
    ws.destroy()
    return {"deleted": session_id}


# ── Workspace file download ─────────────────────────────────────────────────────

@app.get("/workspace/{session_id}/{file_path:path}")
async def get_workspace_file(session_id: str, file_path: str):
    ws = _sessions.get(session_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="Session not found")
    target = (ws.path / file_path).resolve()
    if not str(target).startswith(str(ws.path.resolve())):
        raise HTTPException(status_code=403, detail="Access denied")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(target, filename=target.name)


# ── Health ──────────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "provider": config.LLM_PROVIDER}
