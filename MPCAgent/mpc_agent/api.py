"""FastAPI service for the MPC configuration agent."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .agent import DeepSeekNotConfiguredError, MPCConfigAgent
from .backends import BackendPlanRequest, BackendPlanResponse, BackendSelector
from .backends.schemas import BackendCapability
from .memory import ConversationState
from .schemas import ChatRequest, ChatResponse, MPCProtocolConfig

app = FastAPI(
    title="MPC Protocol Configuration Agent",
    version="0.1.0",
    description="Generate structured MPC protocol configuration from natural language.",
)

agent = MPCConfigAgent()
backend_selector = BackendSelector(agent.settings)
STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api-info")
def api_info() -> dict[str, Any]:
    return {
        "name": app.title,
        "status": "running",
        "docs": "/docs",
        "health": "/health",
        "chat": {
            "method": "POST",
            "path": "/chat",
            "body": {
                "message": "三方恶意安全MPC，算术电路，Shamir分享...",
                "structured_options": {
                    "participant_scale": "3-party",
                    "circuit_form": "Arithmetic",
                    "adversary_behavior": "Malicious",
                    "network_model": "Synchronous",
                },
                "session_id": "optional-existing-session-id",
                "reset": False,
            },
        },
        "session_endpoints": [
            "GET /sessions",
            "GET /sessions/{session_id}",
            "GET /sessions/{session_id}/config",
            "POST /sessions/{session_id}/reset",
            "DELETE /sessions/{session_id}",
        ],
    }


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "deepseek_configured": bool(agent.settings.deepseek_api_key),
        "model": agent.settings.deepseek_model,
    }


@app.get("/schema")
def config_schema() -> dict:
    return MPCProtocolConfig.model_json_schema()


@app.get("/backends", response_model=list[BackendCapability])
def list_backends() -> list[BackendCapability]:
    return backend_selector.capabilities()


@app.post("/backends/plan", response_model=BackendPlanResponse)
def plan_backend(request: BackendPlanRequest) -> BackendPlanResponse:
    try:
        return backend_selector.plan(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        return await agent.aprocess(request)
    except DeepSeekNotConfiguredError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"LLM call failed: {exc}") from exc


@app.get("/chat")
def chat_usage() -> dict[str, Any]:
    return {
        "message": "Use POST /chat with a JSON body. Open /docs for an interactive test UI.",
        "example": {
            "message": "我要做三方MPC，恶意安全，最多腐化一方，使用算术电路和Shamir秘密分享。",
            "structured_options": {
                "participant_scale": "3-party",
                "circuit_form": "Arithmetic",
                "secret_sharing": "Shamir",
                "adversary_behavior": "Malicious",
            },
            "session_id": None,
            "reset": False,
        },
    }


@app.get("/sessions")
def list_sessions() -> dict[str, list[str]]:
    return {"session_ids": agent.memory_store.list_session_ids()}


@app.get("/sessions/{session_id}", response_model=ConversationState)
def get_session(session_id: str) -> ConversationState:
    state = agent.memory_store.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return state


@app.get("/sessions/{session_id}/config", response_model=MPCProtocolConfig)
def get_session_config(session_id: str) -> MPCProtocolConfig:
    state = agent.memory_store.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return state.current_config


@app.post("/sessions/{session_id}/backend-plan", response_model=BackendPlanResponse)
def plan_session_backend(
    session_id: str,
    request: BackendPlanRequest | None = None,
) -> BackendPlanResponse:
    state = agent.memory_store.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")

    body = request or BackendPlanRequest()
    return backend_selector.plan(
        BackendPlanRequest(
            session_id=session_id,
            config=state.current_config,
            task_hint=body.task_hint,
            preferred_backend=body.preferred_backend,
            execute=body.execute,
        )
    )


@app.post("/sessions/{session_id}/reset")
def reset_session(session_id: str) -> dict[str, str]:
    state = agent.memory_store.reset(session_id)
    return {"session_id": state.session_id, "status": "reset"}


@app.delete("/sessions/{session_id}")
def delete_session(session_id: str) -> dict[str, str]:
    deleted = agent.memory_store.delete(session_id)
    return {"session_id": session_id, "status": "deleted" if deleted else "not_found"}
