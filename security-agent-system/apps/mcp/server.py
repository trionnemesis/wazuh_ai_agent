"""將 LangGraph 工作流程公開為工具的模型內容協定 (MCP) 伺服器。"""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List

from mcp.server import Server
from mcp.types import (
    CallToolResult,
    ListToolsResult,
    TextContent,
    Tool,
)

from security_agent_system.core.config import settings
from security_agent_system.workflows.langgraph import LangGraphOrchestrator

server = Server("security-agent-system")
orchestrator = LangGraphOrchestrator()


@server.on_startup
async def _startup() -> None:
    await orchestrator.initialize()


@server.on_shutdown
async def _shutdown() -> None:
    await orchestrator.stop()


@server.list_tools()
async def list_tools() -> ListToolsResult:
    return ListToolsResult(
        tools=[
            Tool(
                name="process_alert",
                description="透過 LangGraph 協調器處理安全警報",
                input_schema={
                    "type": "object",
                    "properties": {
                        "description": {"type": "string"},
                        "severity": {"type": "string", "default": "medium"},
                        "type": {"type": "string", "default": "mcp"},
                        "source": {"type": "string", "default": "mcp"},
                        "details": {"type": "object", "default": {}},
                        "context": {"type": "object", "default": {}},
                    },
                    "required": ["description"],
                },
            ),
            Tool(
                name="system_status",
                description="返回協調器的健康狀態元資料",
                input_schema={"type": "object", "properties": {}},
            ),
        ]
    )


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any] | None = None) -> CallToolResult:
    arguments = arguments or {}

    if name == "process_alert":
        payload = dict(arguments)
        payload.setdefault("id", f"mcp_{datetime.utcnow().timestamp()}")
        payload.setdefault("timestamp", datetime.utcnow().isoformat())
        payload.setdefault("source", arguments.get("source", "mcp"))
        payload.setdefault("type", arguments.get("type", "mcp"))
        payload.setdefault("severity", arguments.get("severity", "medium"))
        result = await orchestrator.process_manual_alert(payload)
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=json.dumps(result, indent=2, default=str),
                )
            ]
        )

    if name == "system_status":
        status = {
            "environment": settings.environment,
            "graph_initialized": orchestrator.graph is not None,
            "llm_providers": list(orchestrator.llm_providers.keys()),
            "infrastructure": list(orchestrator.infrastructure.keys()),
            "timestamp": datetime.utcnow().isoformat(),
        }
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(status, indent=2))]
        )

    raise ValueError(f"未知的工具：{name}")


async def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    await server.serve(host=host, port=port)


def main(argv: List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="啟動 MCP 伺服器")
    parser.add_argument("--host", default="127.0.0.1", help="綁定地址")
    parser.add_argument("--port", default=8765, type=int, help="綁定連接埠")
    args = parser.parse_args(argv)

    asyncio.run(run_server(host=args.host, port=args.port))


if __name__ == "__main__":
    main()