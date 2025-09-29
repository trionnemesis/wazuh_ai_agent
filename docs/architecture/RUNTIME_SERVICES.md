# Runtime Services Overview

This document summarizes the runtime layer introduced during the repository refactor. LangChain, LangGraph, LangServe, and the Model Context Protocol (MCP) work together to offer multiple integration points.

## Service Matrix

| Service | Purpose | Entry Point | Transport | Notes |
| --- | --- | --- | --- | --- |
| CLI Runtime | Operations and local workflows | `apps.cli.main` | Terminal (Click) | Provides orchestration commands and admin tooling |
| LangServe API | Hosted HTTP interface for workflows | `apps.langserve.app` | FastAPI + LangServe | Exposes alert processing as LangChain runnables |
| MCP Server | IDE and tool integration | `apps.mcp.server` | MCP (WebSocket) | Offers tools that trigger LangGraph flows from compliant clients |

## Lifecycle Hooks

- **Startup**: Each runtime initializes `LangGraphOrchestrator` and prepares infrastructure connections on demand. Shared initialization logic lives in `security_agent_system.workflows.langgraph`.
- **Shutdown**: Resources such as message brokers, graph/vector databases, and checkpointers are closed through orchestrator teardown helpers.

## Shared Components

- `LangGraphOrchestrator`: Core orchestrator reused across runtimes.
- `Agent Nodes`: Manager, Hunter, and Executor nodes reused from `security_agent_system.workflows.langgraph.agents`.
- `Settings`: `.env` driven configuration via `security_agent_system.core.config.settings`.

## Extension Points

- **Custom Chains**: Extend LangServe by composing `Runnable` chains around `LangGraphOrchestrator`.
- **MCP Tools**: Register additional tool definitions in `apps.mcp.server` to expose new remediation or investigation capabilities.
- **CLI Plugins**: Add new Click commands in `apps.cli.main` to orchestrate bespoke automation flows.

Refer to [Directory Structure](../reference/DIRECTORY_STRUCTURE.md) for the full package layout.
