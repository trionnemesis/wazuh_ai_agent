"""Agent orchestrator for managing the three-agent system."""
import asyncio
from typing import Dict, Any, List, Optional
import structlog
from datetime import datetime

from ..agents import ManagerAgent, HunterAgent, ExecutorAgent
from ..infrastructure import (
    RabbitMQBroker, KafkaBroker,
    Neo4jDatabase, ChromaDatabase,
    OpenAIProvider, AnthropicProvider, GoogleProvider,
    SlackNotificationService
)
from .action_executor import ActionExecutorService
from ..core.config import settings, MessageBrokerType, LLMProvider
from ..core.models import AlertMessage

logger = structlog.get_logger()


class AgentOrchestrator:
    """Orchestrates the three-agent security system."""
    
    def __init__(self):
        self.agents: Dict[str, Any] = {}
        self.infrastructure: Dict[str, Any] = {}
        self.is_running = False
        
    async def initialize(self) -> None:
        """Initialize all system components."""
        logger.info("Initializing Security Agent System")
        
        # Initialize infrastructure
        await self._initialize_infrastructure()
        
        # Initialize agents
        await self._initialize_agents()
        
        logger.info("System initialization complete")
        
    async def _initialize_infrastructure(self) -> None:
        """Initialize infrastructure components."""
        # Message Broker
        if settings.broker_type == MessageBrokerType.RABBITMQ:
            self.infrastructure["broker"] = RabbitMQBroker()
        else:
            self.infrastructure["broker"] = KafkaBroker()
            
        # Graph Database
        self.infrastructure["graph_db"] = Neo4jDatabase()
        
        # Vector Database
        self.infrastructure["vector_db"] = ChromaDatabase()
        
        # LLM Providers
        self.infrastructure["llm_providers"] = {
            LLMProvider.OPENAI: OpenAIProvider(),
            LLMProvider.ANTHROPIC: AnthropicProvider(),
            LLMProvider.GOOGLE: GoogleProvider()
        }
        
        # Notification Service
        self.infrastructure["notifier"] = SlackNotificationService()
        
        # Action Executor
        self.infrastructure["action_executor"] = ActionExecutorService()
        
        logger.info("Infrastructure components created")
        
    async def _initialize_agents(self) -> None:
        """Initialize the three agents."""
        # Manager Agent
        manager_llm = self.infrastructure["llm_providers"][
            LLMProvider[settings.manager_config["llm_provider"]]
        ]
        
        self.agents["manager"] = ManagerAgent(
            message_broker=self.infrastructure["broker"],
            llm_provider=manager_llm
        )
        
        # Hunter Agent
        hunter_llm = self.infrastructure["llm_providers"][
            LLMProvider[settings.hunter_config["llm_provider"]]
        ]
        
        self.agents["hunter"] = HunterAgent(
            message_broker=self.infrastructure["broker"],
            graph_db=self.infrastructure["graph_db"],
            vector_db=self.infrastructure["vector_db"],
            llm_provider=hunter_llm
        )
        
        # Executor Agent
        executor_llm = self.infrastructure["llm_providers"][
            LLMProvider[settings.executor_config["llm_provider"]]
        ]
        
        self.agents["executor"] = ExecutorAgent(
            message_broker=self.infrastructure["broker"],
            llm_provider=executor_llm,
            notification_service=self.infrastructure["notifier"],
            action_executor=self.infrastructure["action_executor"]
        )
        
        # Initialize all agents
        await asyncio.gather(
            self.agents["manager"].initialize(),
            self.agents["hunter"].initialize(),
            self.agents["executor"].initialize()
        )
        
        logger.info("All agents initialized")
        
    async def start(self) -> None:
        """Start the agent system."""
        if self.is_running:
            logger.warning("System already running")
            return
            
        logger.info("Starting Security Agent System")
        self.is_running = True
        
        # Start all agents
        agent_tasks = [
            asyncio.create_task(self.agents["manager"].start()),
            asyncio.create_task(self.agents["hunter"].start()),
            asyncio.create_task(self.agents["executor"].start())
        ]
        
        # Start monitoring
        monitor_task = asyncio.create_task(self._monitor_system())
        
        # Start API server
        api_task = asyncio.create_task(self._start_api_server())
        
        try:
            # Run until cancelled
            await asyncio.gather(
                *agent_tasks,
                monitor_task,
                api_task
            )
        except asyncio.CancelledError:
            logger.info("System shutdown requested")
        finally:
            self.is_running = False
            
    async def stop(self) -> None:
        """Stop the agent system gracefully."""
        logger.info("Stopping Security Agent System")
        
        # Stop all agents
        await asyncio.gather(
            self.agents["manager"].stop(),
            self.agents["hunter"].stop(),
            self.agents["executor"].stop()
        )
        
        # Disconnect infrastructure
        if "broker" in self.infrastructure:
            await self.infrastructure["broker"].disconnect()
        if "graph_db" in self.infrastructure:
            await self.infrastructure["graph_db"].disconnect()
        if "vector_db" in self.infrastructure:
            await self.infrastructure["vector_db"].disconnect()
            
        self.is_running = False
        logger.info("System stopped")
        
    async def process_alert(self, alert_data: Dict[str, Any]) -> str:
        """Process a new security alert."""
        try:
            # Create alert message
            alert = AlertMessage(**alert_data)
            
            # Send to Manager Agent
            task = await self.agents["manager"].process_alert(alert)
            
            logger.info("Alert processed",
                       task_id=task.task_id,
                       alert_id=alert.alert_id)
                       
            return task.task_id
            
        except Exception as e:
            logger.error("Failed to process alert", error=str(e))
            raise
            
    async def get_system_status(self) -> Dict[str, Any]:
        """Get current system status."""
        status = {
            "is_running": self.is_running,
            "timestamp": datetime.utcnow().isoformat(),
            "agents": {},
            "infrastructure": {}
        }
        
        # Get agent health
        for name, agent in self.agents.items():
            try:
                health = await agent.health_check()
                status["agents"][name] = health
            except Exception as e:
                status["agents"][name] = {
                    "status": "error",
                    "error": str(e)
                }
                
        # Check infrastructure health
        status["infrastructure"]["broker"] = {
            "type": settings.broker_type,
            "host": settings.broker_host,
            "port": settings.broker_port
        }
        
        status["infrastructure"]["graph_db"] = {
            "uri": settings.neo4j_uri,
            "connected": self.infrastructure.get("graph_db") is not None
        }
        
        status["infrastructure"]["vector_db"] = {
            "host": settings.chroma_host,
            "port": settings.chroma_port,
            "connected": self.infrastructure.get("vector_db") is not None
        }
        
        return status
        
    async def _monitor_system(self) -> None:
        """Monitor system health and performance."""
        while self.is_running:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                # Get system status
                status = await self.get_system_status()
                
                # Check for issues
                issues = []
                
                for agent_name, agent_status in status["agents"].items():
                    if agent_status.get("status") != "healthy":
                        issues.append(f"Agent {agent_name} is not healthy")
                        
                # Alert if issues found
                if issues:
                    logger.warning("System health issues detected",
                                 issues=issues)
                                 
                    # Send notification
                    if self.infrastructure.get("notifier"):
                        await self.infrastructure["notifier"].send_alert(
                            title="System Health Alert",
                            message=f"Issues detected: {', '.join(issues)}",
                            severity="warning"
                        )
                        
            except Exception as e:
                logger.error("System monitoring error", error=str(e))
                
    async def _start_api_server(self) -> None:
        """Start the API server for external interactions."""
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import JSONResponse
        import uvicorn
        
        app = FastAPI(title="Security Agent System API")
        
        @app.get("/health")
        async def health_check():
            """System health check endpoint."""
            return await self.get_system_status()
            
        @app.post("/alerts")
        async def submit_alert(alert_data: Dict[str, Any]):
            """Submit a new security alert."""
            try:
                task_id = await self.process_alert(alert_data)
                return {"task_id": task_id, "status": "accepted"}
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))
                
        @app.get("/tasks/{task_id}")
        async def get_task_status(task_id: str):
            """Get task status."""
            # Check with Manager Agent
            manager = self.agents.get("manager")
            if not manager:
                raise HTTPException(status_code=503, detail="Manager agent not available")
                
            task = manager.active_tasks.get(task_id) or next(
                (t for t in manager.task_history if t.task_id == task_id), None
            )
            
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
                
            return task.dict()
            
        @app.post("/approvals/{request_id}")
        async def handle_approval(request_id: str, approval_data: Dict[str, Any]):
            """Handle approval response."""
            executor = self.agents.get("executor")
            if not executor:
                raise HTTPException(status_code=503, detail="Executor agent not available")
                
            await executor.handle_approval_response(
                request_id=request_id,
                approved=approval_data.get("approved", False),
                approver=approval_data.get("approver", "unknown"),
                comments=approval_data.get("comments")
            )
            
            return {"status": "processed"}
            
        @app.get("/metrics")
        async def get_metrics():
            """Get system metrics."""
            metrics = {}
            
            for name, agent in self.agents.items():
                metrics[name] = agent.metrics
                
            return metrics
            
        # Run server
        config = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info"
        )
        server = uvicorn.Server(config)
        
        logger.info("API server starting on port 8000")
        await server.serve()
        
    async def handle_approval_callback(
        self,
        request_id: str,
        approved: bool,
        approver: str,
        comments: Optional[str] = None
    ) -> None:
        """Handle approval callbacks from external systems."""
        executor = self.agents.get("executor")
        if executor:
            await executor.handle_approval_response(
                request_id, approved, approver, comments
            )
        else:
            logger.error("Executor agent not available for approval callback")
