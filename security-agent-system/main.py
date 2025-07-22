"""Main entry point for the Security Agent System."""
import asyncio
import signal
import sys
from typing import Optional
import structlog
import click
from pathlib import Path

from src.services import AgentOrchestrator
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
orchestrator: Optional[AgentOrchestrator] = None


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
    """Security Agent System - GraphRAG & Agential RAG Hybrid Architecture"""
    pass


@cli.command()
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file path')
def start(config):
    """Start the Security Agent System"""
    global orchestrator
    
    # Load configuration if provided
    if config:
        import os
        from dotenv import load_dotenv
        load_dotenv(config)
        
    logger.info("Starting Security Agent System",
               environment=settings.environment,
               broker_type=settings.broker_type)
               
    # Create orchestrator
    orchestrator = AgentOrchestrator()
    
    # Setup signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig, lambda s=sig: asyncio.create_task(shutdown(s))
        )
        
    try:
        # Run the system
        loop.run_until_complete(orchestrator.initialize())
        loop.run_until_complete(orchestrator.start())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error("System error", error=str(e), exc_info=True)
    finally:
        loop.close()
        

@cli.command()
@click.option('--alert-file', '-f', type=click.Path(exists=True), 
              help='JSON file containing alert data')
@click.option('--title', '-t', help='Alert title')
@click.option('--description', '-d', help='Alert description')
@click.option('--severity', '-s', 
              type=click.Choice(['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']),
              default='MEDIUM',
              help='Alert severity')
def submit_alert(alert_file, title, description, severity):
    """Submit a test alert to the system"""
    import json
    import httpx
    
    # Build alert data
    if alert_file:
        with open(alert_file, 'r') as f:
            alert_data = json.load(f)
    else:
        alert_data = {
            "alert_id": f"test_{asyncio.get_event_loop().time()}",
            "source": "cli_test",
            "timestamp": "2024-01-20T10:00:00Z",
            "severity": severity,
            "title": title or "Test Alert from CLI",
            "description": description or "This is a test alert submitted via CLI",
            "raw_data": {},
            "affected_assets": ["test-host-01"],
            "source_ips": ["192.168.1.100"],
            "destination_ips": ["10.0.0.50"],
            "user_accounts": ["test-user"],
            "file_hashes": []
        }
        
    # Submit to API
    try:
        response = httpx.post("http://localhost:8000/alerts", json=alert_data)
        response.raise_for_status()
        result = response.json()
        
        click.echo(f"Alert submitted successfully. Task ID: {result['task_id']}")
        
    except Exception as e:
        click.echo(f"Failed to submit alert: {e}", err=True)
        sys.exit(1)
        

@cli.command()
def status():
    """Check system status"""
    import httpx
    
    try:
        response = httpx.get("http://localhost:8000/health")
        response.raise_for_status()
        status = response.json()
        
        click.echo("System Status:")
        click.echo(f"  Running: {status['is_running']}")
        click.echo(f"  Timestamp: {status['timestamp']}")
        
        click.echo("\nAgent Status:")
        for agent, health in status['agents'].items():
            click.echo(f"  {agent}: {health.get('status', 'unknown')}")
            
        click.echo("\nInfrastructure:")
        for component, info in status['infrastructure'].items():
            click.echo(f"  {component}: {info}")
            
    except Exception as e:
        click.echo(f"Failed to get status: {e}", err=True)
        sys.exit(1)
        

@cli.command()
def test():
    """Run system tests"""
    import pytest
    
    # Run pytest
    exit_code = pytest.main(["-v", "tests/"])
    sys.exit(exit_code)
    

@cli.command()
def simulate():
    """Run attack simulation"""
    import random
    import time
    import httpx
    
    click.echo("Starting attack simulation...")
    
    # Simulation scenarios
    scenarios = [
        {
            "title": "Suspicious Lateral Movement Detected",
            "description": "Multiple RDP connections from single source to various internal hosts",
            "severity": "HIGH",
            "affected_assets": ["srv-db-01", "srv-web-02", "srv-app-03"],
            "source_ips": ["10.10.1.50"],
            "suspected_category": "LATERAL_MOVEMENT"
        },
        {
            "title": "Potential Data Exfiltration",
            "description": "Large data transfer to unknown external IP",
            "severity": "CRITICAL",
            "affected_assets": ["srv-db-01"],
            "destination_ips": ["185.220.101.50"],
            "suspected_category": "DATA_EXFILTRATION"
        },
        {
            "title": "Malware Execution Detected",
            "description": "Known malware hash executed on endpoint",
            "severity": "HIGH",
            "affected_assets": ["wks-user-100"],
            "file_hashes": ["d41d8cd98f00b204e9800998ecf8427e"],
            "suspected_category": "MALWARE"
        }
    ]
    
    # Submit alerts
    for i, scenario in enumerate(scenarios):
        alert_data = {
            "alert_id": f"sim_{int(time.time())}_{i}",
            "source": "simulation",
            "timestamp": f"2024-01-20T{10+i}:00:00Z",
            "severity": scenario["severity"],
            "title": scenario["title"],
            "description": scenario["description"],
            "raw_data": {"simulation": True},
            "affected_assets": scenario.get("affected_assets", []),
            "source_ips": scenario.get("source_ips", []),
            "destination_ips": scenario.get("destination_ips", []),
            "user_accounts": scenario.get("user_accounts", []),
            "file_hashes": scenario.get("file_hashes", []),
            "suspected_category": scenario.get("suspected_category")
        }
        
        try:
            response = httpx.post("http://localhost:8000/alerts", json=alert_data)
            response.raise_for_status()
            result = response.json()
            
            click.echo(f"✓ Alert {i+1} submitted: {scenario['title']} (Task ID: {result['task_id']})")
            
            # Wait between alerts
            time.sleep(random.randint(2, 5))
            
        except Exception as e:
            click.echo(f"✗ Failed to submit alert {i+1}: {e}", err=True)
            
    click.echo("\nSimulation complete!")
    

if __name__ == "__main__":
    cli()
