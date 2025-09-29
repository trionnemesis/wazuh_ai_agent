# Security Agent System - LangGraph Multi-Agent Orchestration

A state-of-the-art security orchestration system built with LangChain's LangGraph framework. This system implements a directed acyclic graph (DAG) for coordinating three specialized AI agents that work together to detect, investigate, and remediate security threats.

## 🏗️ Architecture Overview

The system uses LangGraph to orchestrate three intelligent agents:

1. **Manager Agent**: Analyzes alerts and coordinates response
2. **Hunter Agent**: Performs deep threat investigation  
3. **Executor Agent**: Executes remediation actions

### Workflow Graph

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

## ✨ Key Features

- **LangGraph DAG**: State-based workflow with conditional routing
- **LCEL Chains**: Composable AI operations using LangChain Expression Language
- **State Persistence**: Automatic checkpointing for failure recovery
- **Human-in-the-Loop**: Built-in approval workflows for high-risk actions
- **Parallel Processing**: Efficient batch alert processing
- **Multi-LLM Support**: Configure different LLMs per agent (OpenAI, Anthropic, Google)

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Docker and Docker Compose
- API keys for LLM providers (OpenAI/Anthropic/Google)

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd security-agent-system

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys and settings

# Start infrastructure
docker-compose up -d

# Run the CLI orchestrator
python main.py start

# Launch LangServe API
python main.py serve-langserve

# Launch MCP server
python main.py serve-mcp
```

## 🧪 Testing the System

### Send a test alert:
```bash
python main.py test-alert \
    --severity high \
    --type malware \
    --source endpoint \
    "Ransomware detected on production server"
```

### Check system status:
```bash
python main.py status
```

### Visualize the workflow:
```bash
python main.py visualize --output workflow.png
```

## 📁 Project Structure

```
security-agent-system/
├── apps/
│   ├── cli/                # Click-based CLI entrypoints
│   ├── langserve/          # LangServe FastAPI application
│   └── mcp/                # Model Context Protocol server
├── security_agent_system/
│   ├── agents/             # Manager, Hunter, Executor implementations
│   ├── core/               # Settings, models, and enums
│   ├── infrastructure/     # Brokers, databases, notifications
│   ├── services/           # Support services and orchestrators
│   └── workflows/
│       └── langgraph/      # LangGraph DAG, state, and nodes
├── tests/                  # Test suite
├── config/                 # Environment templates and configs
├── docker-compose.yml      # Infrastructure setup
├── main.py                 # CLI shim (imports apps.cli.main)
└── requirements.txt        # Python dependencies
```

## 🔧 Configuration

The system is configured through environment variables in `.env`:

```bash
# LLM Configuration
DEFAULT_LLM_PROVIDER=openai
OPENAI_API_KEY=your-openai-key
ANTHROPIC_API_KEY=your-anthropic-key
GOOGLE_API_KEY=your-google-key

# Agent-specific LLMs
MANAGER_LLM_PROVIDER=openai
HUNTER_LLM_PROVIDER=anthropic
EXECUTOR_LLM_PROVIDER=google

# Infrastructure
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
CHROMADB_PATH=./chroma_db
MESSAGE_BROKER_TYPE=rabbitmq
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

# Notifications
SLACK_WEBHOOK_URL=your-webhook-url
```

## 📊 Monitoring

The system provides comprehensive monitoring through Prometheus metrics:

- Alert processing rates
- Agent performance metrics
- Workflow execution times
- Error rates and types

Access monitoring dashboards:
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000

## 🤖 Agent Details

### Manager Agent
- **Role**: Central coordinator and decision maker
- **Capabilities**:
  - Alert severity assessment
  - Workflow routing decisions
  - Remediation plan creation
  - Investigation result review

### Hunter Agent
- **Role**: Threat investigation specialist
- **Capabilities**:
  - Graph database queries (Neo4j)
  - Vector similarity search (ChromaDB)
  - Threat intelligence lookups
  - Attack pattern identification

### Executor Agent
- **Role**: Remediation action executor
- **Capabilities**:
  - Action planning and validation
  - Security control execution
  - Rollback management
  - Result verification

## 🔄 Workflow States

The system maintains a comprehensive state that flows through the graph:

- `current_alert`: Alert being processed
- `investigations`: Investigation results
- `remediation_plans`: Planned actions
- `execution_results`: Action outcomes
- `workflow_history`: Complete audit trail

## 🛠️ Development

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=security_agent_system tests/

# Run specific test module
pytest tests/test_agents.py
```

### Adding New Actions
1. Add action to `ExecutorNode.action_registry`
2. Implement action method
3. Update action documentation
4. Add tests

### Extending the Graph
1. Define new nodes in the graph
2. Add routing logic
3. Update state definitions
4. Test the new workflow

## 📚 Documentation

- [Platform Architecture](../docs/architecture/PLATFORM_ARCHITECTURE.md)
- [LangGraph Workflow](../docs/architecture/LANGGRAPH_WORKFLOW.md)
- [Runtime Services Overview](../docs/architecture/RUNTIME_SERVICES.md)
- [Deployment Guide](../docs/guides/DEPLOYMENT.md)
- [Monitoring Guide](../docs/guides/MONITORING.md)
- [LangServe Deployment](../docs/guides/LANGSERVE_DEPLOYMENT.md)
- [MCP Server Operations](../docs/guides/MCP_SERVER_GUIDE.md)
- [Document Catalog](../docs/reference/DOCUMENT_CATALOG.md)

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

Built with:
- [LangChain](https://langchain.com/) - LLM application framework
- [LangGraph](https://github.com/langchain-ai/langgraph) - Multi-agent orchestration
- [Neo4j](https://neo4j.com/) - Graph database for threat relationships
- [ChromaDB](https://www.trychroma.com/) - Vector database for similarity search
