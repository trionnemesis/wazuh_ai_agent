"""FastAPI application exposing LangGraph workflows via LangServe."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from fastapi import FastAPI
from langchain_core.runnables import RunnableLambda
from langserve import add_routes
from pydantic import BaseModel, Field

from security_agent_system.core.config import settings
from security_agent_system.workflows.langgraph import LangGraphOrchestrator

app = FastAPI(
    title="Security Agent LangServe",
    description="Hosted LangGraph workflows for automated security orchestration",
    version="1.0.0",
)


class AlertInput(BaseModel):
    """Schema for incoming security alerts."""

    description: str = Field(..., description="Human-readable alert description")
    severity: str = Field("medium", description="Severity label: critical/high/medium/low/info")
    type: str = Field("manual", description="Alert type identifier")
    source: str = Field("langserve", description="Alert source identifier")
    details: Dict[str, Any] = Field(default_factory=dict, description="Alert details payload")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context metadata")


orchestrator = LangGraphOrchestrator()


async def _ensure_initialized() -> None:
    """Initialize orchestrator lazily for LangServe requests."""
    if orchestrator.graph is None:
        await orchestrator.initialize()


async def _process_alert(alert: AlertInput) -> Dict[str, Any]:
    await _ensure_initialized()
    payload = alert.dict()
    payload.setdefault("id", f"langserve_{datetime.utcnow().timestamp()}")
    payload.setdefault("timestamp", datetime.utcnow().isoformat())
    return await orchestrator.process_manual_alert(payload)


alert_runnable = RunnableLambda(_process_alert)
add_routes(app, alert_runnable.with_types(input_type=AlertInput), path="/alerts")


@app.on_event("shutdown")
async def shutdown_event() -> None:
    if orchestrator.is_running or orchestrator.graph is not None:
        await orchestrator.stop()


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    return {
        "status": "ok",
        "environment": settings.environment,
        "graph_initialized": orchestrator.graph is not None,
        "llm_providers": list(orchestrator.llm_providers.keys()),
    }


@app.get("/runtime/status")
async def runtime_status() -> Dict[str, Any]:
    await _ensure_initialized()
    return {
        "is_running": orchestrator.is_running,
        "checkpointer": orchestrator.checkpointer is not None,
        "infrastructure": list(orchestrator.infrastructure.keys()),
        "timestamp": datetime.utcnow().isoformat(),
    }
