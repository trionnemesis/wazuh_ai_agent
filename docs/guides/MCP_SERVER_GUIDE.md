# MCP Server Operations Guide

The Model Context Protocol (MCP) server allows IDEs and command palettes to trigger LangGraph workflows.

## Prerequisites
- Install dependencies:
  ```bash
  pip install -r security-agent-system/requirements.txt
  ```
- Ensure network access to message brokers, Neo4j, and ChromaDB instances.

## Running the Server
```bash
python -m apps.mcp.server --host 0.0.0.0 --port 8765
```

### Flags
- `--host` – Bind address (default `127.0.0.1`).
- `--port` – WebSocket port for MCP clients (default `8765`).

## Available Tools
- `process_alert` – Accepts alert payloads and returns structured LangGraph results.
- `system_status` – Returns orchestrator health metadata for diagnostics.

## Integrating with IDEs
1. Configure your MCP-capable IDE (Cursor, Windsurf, etc.) to connect to the server endpoint.
2. Authenticate using environment variables or local credentials if required by the IDE.
3. Invoke the `process_alert` tool from the IDE to send alert data directly to LangGraph.

## Operational Tips
- Monitor Structlog output for tool invocation traces.
- Run behind a process manager (systemd, supervisord) for resilience.
- Use TLS termination when exposing the server beyond localhost.
