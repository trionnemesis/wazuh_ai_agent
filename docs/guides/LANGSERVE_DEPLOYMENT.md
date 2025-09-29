# LangServe Deployment Guide

This guide covers launching the LangServe-powered API that wraps the LangGraph orchestrator.

## Prerequisites
- Python 3.10+
- Dependencies from `security-agent-system/requirements.txt`
- Valid environment variables for LLM providers and infrastructure backends

## Quick Start
1. Install dependencies:
   ```bash
   pip install -r security-agent-system/requirements.txt
   ```
2. Set environment configuration (see `.env.example`).
3. Run the LangServe application:
   ```bash
   uvicorn apps.langserve.app:app --host 0.0.0.0 --port 8001
   ```
4. Interact with the LangServe UI at `http://localhost:8001/docs` or `http://localhost:8001/playground`.

## Endpoints
- `POST /alerts/invoke` – Submit a security alert payload and receive orchestration results.
- `GET /health` – Platform health check, including orchestrator readiness.
- `GET /runtime/status` – Snapshot of LangGraph runtime metadata.

## Scaling Tips
- Run behind a reverse proxy (NGINX) for TLS termination.
- Configure Uvicorn workers based on CPU cores: `uvicorn ... --workers 2`.
- Use environment variables to select broker and database backends per deployment stage.

## Observability
- FastAPI logs are enriched with Structlog context.
- Prometheus metrics are exposed under `/metrics` (mount your collector accordingly).
- LangServe run traces automatically propagate to LangSmith when configured.
