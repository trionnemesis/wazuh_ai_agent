"""Main entry point for the Security Agent System with LangGraph."""
import asyncio
import signal
import sys
from typing import Optional
import structlog
import click
from pathlib import Path

from src.langgraph import LangGraphOrchestrator
from src.core.config import settings
from src.core.models import AlertMessage, AlertSeverity

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Global orchestrator instance
orchestrator: Optional[LangGraphOrchestrator] = None


async def shutdown(signal_received):
    """Graceful shutdown handler."""
    logger.info(f"Received signal {signal_received.name}, shutting down...")
    
    if orchestrator:
        await orchestrator.stop()
        
    # Cancel all running tasks
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
        
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("Shutdown complete")


@click.group()
def cli():
    """Security Agent System with LangGraph Multi-Agent Orchestration."""
    pass


@cli.command()
@click.option('--config', type=click.Path(exists=True), help='Path to configuration file')
def start(config):
    """Start the Security Agent System."""
    global orchestrator
    
    # Load configuration if provided
    if config:
        settings.load_from_file(config)
    
    logger.info("Starting Security Agent System with LangGraph",
                environment=settings.environment,
                broker_type=settings.broker_type,
                default_llm=settings.default_llm_provider)
    
    # Create orchestrator
    orchestrator = LangGraphOrchestrator()
    
    # Setup signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig, lambda s=sig: asyncio.create_task(shutdown(s))
        )
    
    try:
        # Run the system
        loop.run_until_complete(run_system())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error("System error", error=str(e), exc_info=True)
    finally:
        loop.close()


async def run_system():
    """Run the main system loop."""
    try:
        # Initialize the orchestrator
        await orchestrator.initialize()
        
        # Start the orchestrator
        await orchestrator.start()
        
        logger.info("System is running. Press Ctrl+C to stop.")
        
        # Keep running until shutdown
        while True:
            await asyncio.sleep(1)
            
    except asyncio.CancelledError:
        logger.info("System loop cancelled")
        raise
    except Exception as e:
        logger.error("Fatal error in system loop", error=str(e), exc_info=True)
        raise


@cli.command()
@click.option('--severity', type=click.Choice(['critical', 'high', 'medium', 'low', 'info']), 
              default='medium', help='Alert severity')
@click.option('--type', default='manual_test', help='Alert type')
@click.option('--source', default='cli', help='Alert source')
@click.argument('description')
def test_alert(severity, type, source, description):
    """Send a test alert to the system."""
    global orchestrator
    
    logger.info("Sending test alert", 
                severity=severity,
                type=type,
                description=description)
    
    # Create orchestrator for single alert
    orchestrator = LangGraphOrchestrator()
    
    # Create alert
    alert_data = {
        "severity": severity,
        "type": type,
        "source": source,
        "description": description,
        "details": {
            "test": True,
            "cli_generated": True
        },
        "context": {
            "user": "cli_test",
            "purpose": "system_test"
        }
    }
    
    # Run async function
    loop = asyncio.get_event_loop()
    
    async def process_test_alert():
        try:
            await orchestrator.initialize()
            result = await orchestrator.process_manual_alert(alert_data)
            
            logger.info("Test alert processed",
                       status=result.get("status"),
                       workflow_steps=len(result.get("workflow_history", [])))
            
            # Print results
            print("\n=== Alert Processing Results ===")
            print(f"Alert ID: {result.get('alert_id')}")
            print(f"Status: {result.get('status')}")
            
            if result.get('investigation'):
                print(f"\nInvestigation Risk Score: {result['investigation'].risk_score}")
                print(f"Affected Assets: {', '.join(result['investigation'].affected_assets)}")
                print(f"Recommendations: {', '.join(result['investigation'].recommendations)}")
            
            if result.get('execution_results'):
                print(f"\nExecuted Actions: {len(result['execution_results'])}")
                for action in result['execution_results']:
                    print(f"  - {action['action_id']}: {action['status']}")
            
            print("\n=== Workflow History ===")
            for step in result.get('workflow_history', []):
                print(f"{step['timestamp']}: {step['step']}")
                
        except Exception as e:
            logger.error("Failed to process test alert", error=str(e), exc_info=True)
        finally:
            await orchestrator.stop()
    
    loop.run_until_complete(process_test_alert())
    loop.close()


@cli.command()
def status():
    """Check system status."""
    logger.info("Checking system status")
    
    # Check configuration
    print("\n=== Configuration Status ===")
    print(f"Environment: {settings.environment}")
    print(f"Message Broker: {settings.broker_type}")
    print(f"Default LLM: {settings.default_llm_provider}")
    print(f"LLM Model: {settings.default_llm_model}")
    
    # Check API keys
    print("\n=== API Key Status ===")
    print(f"OpenAI: {'✓' if settings.openai_api_key else '✗'}")
    print(f"Anthropic: {'✓' if settings.anthropic_api_key else '✗'}")
    print(f"Google: {'✓' if settings.google_api_key else '✗'}")
    
    # Check services
    print("\n=== Service Configuration ===")
    print(f"Neo4j URI: {settings.neo4j_uri}")
    print(f"ChromaDB Path: {settings.chromadb_path}")
    print(f"Slack Webhook: {'✓' if settings.slack_webhook_url else '✗'}")
    
    # Check agent configuration
    print("\n=== Agent Configuration ===")
    print(f"Manager LLM: {settings.manager_config['llm_provider']}")
    print(f"Hunter LLM: {settings.hunter_config['llm_provider']}")
    print(f"Executor LLM: {settings.executor_config['llm_provider']}")
    
    print("\n=== LangGraph Features ===")
    print("✓ LCEL (LangChain Expression Language) for chain composition")
    print("✓ LangGraph DAG for multi-agent orchestration")
    print("✓ State persistence with checkpointing")
    print("✓ Parallel agent execution")
    print("✓ Human-in-the-loop approval workflow")
    print("✓ Error handling and retry logic")


@cli.command()
@click.option('--output', type=click.Path(), default='langgraph_visualization.png',
              help='Output path for graph visualization')
def visualize(output):
    """Visualize the LangGraph DAG structure."""
    logger.info("Generating LangGraph visualization")
    
    try:
        from src.langgraph import SecurityAgentGraph, ManagerNode, HunterNode, ExecutorNode
        
        # Create dummy nodes for visualization
        manager = ManagerNode(llm_provider=None)
        hunter = HunterNode(llm_provider=None)
        executor = ExecutorNode(llm_provider=None)
        
        # Create graph
        graph = SecurityAgentGraph(
            manager_node=manager,
            hunter_node=hunter,
            executor_node=executor
        )
        
        # Get mermaid representation
        mermaid_graph = graph.app.get_graph().draw_mermaid()
        
        print("\n=== LangGraph Structure (Mermaid) ===")
        print(mermaid_graph)
        
        # Try to generate PNG if graphviz is available
        try:
            from langgraph.graph import END
            graph_viz = graph.app.get_graph()
            graph_viz.draw_png(output)
            print(f"\nGraph visualization saved to: {output}")
        except Exception as e:
            print(f"\nCould not generate PNG (install graphviz): {e}")
            print("You can use the Mermaid diagram above in any Mermaid viewer")
            
    except Exception as e:
        logger.error("Failed to generate visualization", error=str(e))
        print(f"Error: {e}")


if __name__ == "__main__":
    cli()
