# Directory Structure

```
security-agent-system/
├── apps/
│   ├── cli/                # Click-based CLI entrypoints
│   ├── langserve/          # LangServe FastAPI deployment
│   └── mcp/                # Model Context Protocol server
├── config/                 # Environment templates and runtime configuration
├── examples/               # Example alerts and workflows for demos
├── requirements.txt        # Project dependencies (LangChain, LangGraph, LangServe, MCP)
├── security_agent_system/
│   ├── agents/             # Manager, Hunter, Executor agent implementations
│   ├── core/               # Settings, domain models, enums
│   ├── infrastructure/     # Message brokers, databases, notification bridges
│   ├── services/           # Supporting services (action executor, orchestration helpers)
│   └── workflows/
│       └── langgraph/      # LangGraph DAG, nodes, and orchestrator
├── tests/                  # Pytest suites covering agent behaviors
└── start.sh                # Bootstrap helper for containerized deployments
```

### Ownership Map
- **Workflow Engineering** – `security_agent_system/workflows/langgraph`
- **Runtime Services** – `apps/langserve`, `apps/mcp`
- **Core Domain Models** – `security_agent_system/core`
- **Infrastructure Integrations** – `security_agent_system/infrastructure`
- **Operations Tooling** – `docs/operations` and `docs/guides`

### Key Entry Points
- CLI: `python security-agent-system/main.py ...`
- LangServe API: `uvicorn apps.langserve.app:app --reload`
- MCP Server: `python -m apps.mcp.server`
