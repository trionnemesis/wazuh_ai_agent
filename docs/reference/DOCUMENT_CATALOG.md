# Document Catalog

The documentation set is organized around the new platform layout that aligns LangChain, LangGraph, LangServe, and MCP runtime responsibilities.

## Architecture & Runtime
- [Platform Architecture](../architecture/PLATFORM_ARCHITECTURE.md) – Core system domains, deployment topology, and shared services.
- [LangGraph Workflow](../architecture/LANGGRAPH_WORKFLOW.md) – Graph state machine, node responsibilities, and LCEL usage patterns.
- [Runtime Services](../architecture/RUNTIME_SERVICES.md) – LangServe and MCP service boundaries plus orchestration lifecycle expectations.

## Guides & Playbooks
- [Deployment Guide](../guides/DEPLOYMENT.md) – End-to-end installation and environment provisioning.
- [Monitoring Guide](../guides/MONITORING.md) – Metrics, alerting, and Grafana dashboards.
- [LangServe Deployment](../guides/LANGSERVE_DEPLOYMENT.md) – Running the hosted API powered by LangServe.
- [MCP Server Operations](../guides/MCP_SERVER_GUIDE.md) – Operating the Model Context Protocol server for IDE integrations.

## Operational Toolkits
- [Testing Strategy](../operations/TESTING_STRATEGY.md) – Validation approach and automation strategy.
- [Intelligent Caching Implementation](../operations/INTELLIGENT_CACHING_IMPLEMENTATION.md) – Cache layers and performance considerations.
- Docker Playbooks
  - [Migration Guide](../operations/docker/MIGRATION_GUIDE.md)
  - [Optimization Guide](../operations/docker/OPTIMIZATION_GUIDE.md)
  - [Optimization Summary](../operations/docker/OPTIMIZATION_SUMMARY.md)

## Reports & Postmortems
- [Project Reports Overview](../reports/PROJECT_REPORTS.md) – Index of historical deliverables.
- [Refactoring Summary](../reports/REFACTORING_SUMMARY.md) – Outcomes from iterative codebase cleanup.
- [Automation Optimization Report](../reports/AUTOMATION_OPTIMIZATION_REPORT.md)
- [Cleanup Completion Report](../reports/CLEANUP_COMPLETION_REPORT.md)
- [Intelligent Caching Report](../reports/INTELLIGENT_CACHING_REPORT.md)
- [Testing Optimization Report](../reports/TESTING_OPTIMIZATION_REPORT.md)

## Reference
- [Directory Structure](DIRECTORY_STRUCTURE.md) – Source tree layout and ownership boundaries.
- [Change Log](../reports/REFACTORING_SUMMARY.md#changelog) – Highlights from recent iterations.

### Quick Start Paths
- **New Engineers**: Review the architecture trio, then follow the Deployment Guide and LangServe Deployment steps.
- **Operations**: Monitor health via the Monitoring Guide and MCP Server Operations checklists.
- **Integrators**: Use the Directory Structure reference to locate APIs, agents, and runtime entrypoints.
