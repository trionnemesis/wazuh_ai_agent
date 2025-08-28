# Document Catalog

## Architecture & Design
- [Architecture Overview](ARCHITECTURE.md) - Core system architecture and components
- [LangGraph Architecture](LANGGRAPH_ARCHITECTURE.md) - LangGraph-based multi-agent orchestration
- [Testing Strategy](TESTING_STRATEGY.md) - Comprehensive testing approach and guidelines

## Deployment & Operations
- [Deployment Guide](DEPLOYMENT.md) - Complete deployment instructions and configurations
- [Monitoring Guide](MONITORING.md) - System monitoring, metrics, and alerting setup
- [Docker Migration Guide](DOCKER_MIGRATION_GUIDE.md) - Docker containerization instructions

## Optimization Reports
- [Docker Optimization Guide](DOCKER_OPTIMIZATION_GUIDE.md) - Docker performance optimization
- [Docker Optimization Summary](DOCKER_OPTIMIZATION_SUMMARY.md) - Key optimization results
- [Testing Optimization Report](TESTING_OPTIMIZATION_REPORT.md) - Test suite improvements
- [Automation Optimization Report](AUTOMATION_OPTIMIZATION_REPORT.md) - CI/CD enhancements
- [Intelligent Caching Implementation](INTELLIGENT_CACHING_IMPLEMENTATION.md) - Caching system design
- [Intelligent Caching Report](INTELLIGENT_CACHING_REPORT.md) - Cache performance analysis

## Project Reports
- [Project Reports Overview](PROJECT_REPORTS.md) - Summary of all project reports
- [Refactoring Summary](REFACTORING_SUMMARY.md) - Code refactoring outcomes
- [Cleanup Completion Report](CLEANUP_COMPLETION_REPORT.md) - Project cleanup status

## Quick Links

### Getting Started
1. Read the [LangGraph Architecture](LANGGRAPH_ARCHITECTURE.md) for the latest system design
2. Follow the [Deployment Guide](DEPLOYMENT.md) for installation
3. Configure monitoring using the [Monitoring Guide](MONITORING.md)

### For Developers
- [Architecture Overview](ARCHITECTURE.md) - Understand the system design
- [LangGraph Architecture](LANGGRAPH_ARCHITECTURE.md) - Learn about the multi-agent orchestration
- [Testing Strategy](TESTING_STRATEGY.md) - Write and run tests
- [Docker Migration Guide](DOCKER_MIGRATION_GUIDE.md) - Container development

### For Operations
- [Deployment Guide](DEPLOYMENT.md) - Deploy and configure the system
- [Monitoring Guide](MONITORING.md) - Set up monitoring and alerts
- [Docker Optimization Guide](DOCKER_OPTIMIZATION_GUIDE.md) - Optimize performance

### Key Technologies
- **LangChain & LangGraph**: Multi-agent orchestration framework
- **LCEL**: LangChain Expression Language for chain composition
- **GraphRAG**: Neo4j for relationship mapping
- **Vector Search**: ChromaDB for similarity search
- **Message Queue**: RabbitMQ/Kafka for event streaming
- **Monitoring**: Prometheus & Grafana

### System Components

#### Core Agents (LangGraph Nodes)
1. **Manager Agent**: Coordinates security response and decision-making
2. **Hunter Agent**: Performs deep threat investigation and analysis
3. **Executor Agent**: Executes remediation actions and validations

#### Infrastructure
- **LangGraph DAG**: Directed acyclic graph for agent orchestration
- **State Management**: Persistent state with checkpointing
- **LLM Providers**: OpenAI, Anthropic, Google (configurable per agent)
- **Databases**: Neo4j (graph), ChromaDB (vector)
- **Message Brokers**: RabbitMQ, Kafka
- **Notifications**: Slack integration

### Recent Updates
- Migrated to LangChain LangGraph for multi-agent orchestration
- Implemented LCEL chains for all agent operations
- Added state persistence and checkpointing
- Introduced human-in-the-loop approval workflows
- Enhanced error handling with graph-level routing
- Added parallel processing capabilities

### Documentation Standards
- All documents use Markdown format
- Code examples include syntax highlighting
- Diagrams use Mermaid format where applicable
- Each guide includes practical examples
- Performance metrics and benchmarks included where relevant