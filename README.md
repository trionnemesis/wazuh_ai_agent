# Security Agent System with LangGraph

[![LangChain](https://img.shields.io/badge/LangChain-0.3.14-blue.svg)](https://langchain.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2.65-green.svg)](https://github.com/langchain-ai/langgraph)
[![LangServe](https://img.shields.io/badge/LangServe-ready-purple.svg)](https://github.com/langchain-ai/langserve)
[![MCP](https://img.shields.io/badge/MCP-integrated-teal.svg)](https://modelcontextprotocol.io/)
[![Neo4j](https://img.shields.io/badge/Neo4j-5.18-red.svg)](https://neo4j.com/)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-0.4.22-orange.svg)](https://www.trychroma.com/)

## 🎯 Overview
A multi-agent security orchestration platform powered by LangChain and LangGraph. The 2025 refactor consolidates the codebase into a reusable package (`security_agent_system`) and introduces dedicated runtime services for CLI operations, LangServe APIs, and MCP integrations.

## 🧱 Project Layout
```
security-agent-system/
├── apps/                       # CLI, LangServe, and MCP entrypoints
├── security_agent_system/      # Core package (agents, core, infrastructure, workflows)
├── tests/                      # Automated test suites
├── config/, examples/          # Deployment assets and runnable samples
└── docs/                       # Architecture, guides, operations, and reports
```
Refer to [Directory Structure](docs/reference/DIRECTORY_STRUCTURE.md) for the complete breakdown.

## 🧠 Architecture

```mermaid
graph TB
    Start([Alert Intake]) --> Manager[Manager Agent]
    Manager -->|investigate| Hunter[Hunter Agent]
    Manager -->|remediate| Executor[Executor Agent]
    Manager -->|dismiss| Complete[Completion]
    Hunter --> Review[Manager Review]
    Review -->|remediate| Executor
    Review -->|escalate| Human[Human Approval]
    Review -->|dismiss| Complete
    Executor -->|completed| Complete
    Executor -->|approval_needed| Human
    Human -->|approved| Executor
    Human -->|rejected| Complete
    Complete --> End([End])
```

### Key Capabilities
- **LangGraph DAG orchestration** with LCEL chains per agent.
- **State persistence** via SQLite checkpoints to support recovery and audit.
- **GraphRAG context** using Neo4j plus ChromaDB for hybrid investigations.
- **Human-in-the-loop workflows** supporting approvals and rollbacks.
- **Modular runtimes** (CLI, LangServe, MCP) that reuse a single orchestrator implementation.

## 🚀 Runtimes
| Runtime | Command | Description |
| --- | --- | --- |
| CLI | `python security-agent-system/main.py start` | Production-grade orchestration with Click commands. |
| LangServe | `uvicorn apps.langserve.app:app --host 0.0.0.0 --port 8001` | REST API powered by LangServe and FastAPI. |
| MCP | `python -m apps.mcp.server --host 127.0.0.1 --port 8765` | Model Context Protocol server for IDE/tool integrations. |

## 🤖 Agent Roles
- **Manager Agent** – Analyses alerts, sets priorities, and builds remediation plans.
- **Hunter Agent** – Performs graph/vector investigations and risk scoring.
- **Executor Agent** – Validates, executes, and monitors remediation tasks.

## 🚀 Quick Start
1. Clone and install dependencies:
   ```bash
   git clone https://github.com/your-org/security-agent-system.git
   cd security-agent-system
   pip install -r security-agent-system/requirements.txt
   ```
2. Configure environment variables (`cp .env.example .env`).
3. Launch supporting services: `docker-compose up -d`.
4. Start your preferred runtime (see table above).

## 📖 Documentation
- [Platform Architecture](docs/architecture/PLATFORM_ARCHITECTURE.md)
- [LangGraph Workflow](docs/architecture/LANGGRAPH_WORKFLOW.md)
- [Runtime Services Overview](docs/architecture/RUNTIME_SERVICES.md)
- [Deployment Guide](docs/guides/DEPLOYMENT.md)
- [Monitoring Guide](docs/guides/MONITORING.md)
- [LangServe Deployment](docs/guides/LANGSERVE_DEPLOYMENT.md)
- [MCP Server Operations](docs/guides/MCP_SERVER_GUIDE.md)
- [Document Catalog](docs/reference/DOCUMENT_CATALOG.md)

## 🧪 Testing
```bash
cd security-agent-system
pytest
```
Trigger a manual alert for smoke testing:
```bash
python security-agent-system/main.py test-alert \
    --severity high \
    --type malware \
    "Suspicious process detected on server"
```

## 🔧 Configuration
Important `.env` variables:
```bash
# LLM Providers
DEFAULT_LLM_PROVIDER=openai
OPENAI_API_KEY=your-key
ANTHROPIC_API_KEY=your-key
GOOGLE_API_KEY=your-key

# Agent Settings
MANAGER_LLM_PROVIDER=openai
HUNTER_LLM_PROVIDER=anthropic
EXECUTOR_LLM_PROVIDER=google

# Infrastructure
NEO4J_URI=bolt://localhost:7687
CHROMADB_PATH=./chroma_db
MESSAGE_BROKER_TYPE=rabbitmq
```

## 📊 Monitoring
Prometheus metrics cover alert throughput, agent performance, execution latency, and error rates. Grafana dashboards are available at `http://localhost:3000`.

## 🤝 Contributing
1. Fork the repository.
2. Create a feature branch.
3. Make changes and add tests.
4. Run `pytest`.
5. Submit a pull request.

## 📄 License
MIT License – see [LICENSE](LICENSE).

## 🙏 Acknowledgments
Built with LangChain, LangGraph, LangServe, MCP, Neo4j, and ChromaDB.
