"""LangGraph-based orchestrator for the Security Agent System."""
import asyncio
from typing import Dict, Any, List, Optional
import structlog
from datetime import datetime
from pathlib import Path

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.aiosqlite import AsyncSqliteSaver

from .graph import SecurityAgentGraph
from .agents import ManagerNode, HunterNode, ExecutorNode
from .state import SecurityAlert, AlertSeverity
from ..core.config import settings, LLMProvider
from ..infrastructure import (
    RabbitMQBroker, KafkaBroker,
    Neo4jDatabase, ChromaDatabase,
    SlackNotificationService
)
from ..services.action_executor import ActionExecutorService

logger = structlog.get_logger()


class LangGraphOrchestrator:
    """Orchestrates the LangGraph-based security agent system."""
    
    def __init__(self):
        """Initialize the LangGraph orchestrator."""
        self.graph: Optional[SecurityAgentGraph] = None
        self.infrastructure: Dict[str, Any] = {}
        self.llm_providers: Dict[str, Any] = {}
        self.checkpointer: Optional[AsyncSqliteSaver] = None
        self.is_running = False
        
    async def initialize(self) -> None:
        """Initialize all system components."""
        logger.info("Initializing LangGraph Security Agent System")
        
        try:
            # Initialize infrastructure
            await self._initialize_infrastructure()
            
            # Initialize LLM providers
            await self._initialize_llm_providers()
            
            # Initialize checkpointer for state persistence
            await self._initialize_checkpointer()
            
            # Create agent nodes
            manager_node = ManagerNode(
                llm_provider=self.llm_providers[settings.manager_config["llm_provider"]]
            )
            
            hunter_node = HunterNode(
                llm_provider=self.llm_providers[settings.hunter_config["llm_provider"]],
                graph_db=self.infrastructure.get("graph_db"),
                vector_db=self.infrastructure.get("vector_db")
            )
            
            executor_node = ExecutorNode(
                llm_provider=self.llm_providers[settings.executor_config["llm_provider"]],
                action_executor=self.infrastructure.get("action_executor"),
                notification_service=self.infrastructure.get("notifier")
            )
            
            # Create the graph
            self.graph = SecurityAgentGraph(
                manager_node=manager_node,
                hunter_node=hunter_node,
                executor_node=executor_node,
                checkpointer=self.checkpointer
            )
            
            logger.info("LangGraph system initialization complete")
            
        except Exception as e:
            logger.error("Failed to initialize LangGraph system", error=str(e), exc_info=True)
            raise
    
    async def _initialize_infrastructure(self) -> None:
        """Initialize infrastructure components."""
        logger.info("Initializing infrastructure components")
        
        # Message Broker
        if settings.broker_type == "rabbitmq":
            self.infrastructure["broker"] = RabbitMQBroker()
        else:
            self.infrastructure["broker"] = KafkaBroker()
        
        # Initialize broker connection
        await self.infrastructure["broker"].connect()
        
        # Graph Database
        self.infrastructure["graph_db"] = Neo4jDatabase()
        await self.infrastructure["graph_db"].connect()
        
        # Vector Database
        self.infrastructure["vector_db"] = ChromaDatabase()
        await self.infrastructure["vector_db"].initialize()
        
        # Notification Service
        self.infrastructure["notifier"] = SlackNotificationService()
        
        # Action Executor
        self.infrastructure["action_executor"] = ActionExecutorService()
        
        logger.info("Infrastructure components initialized")
    
    async def _initialize_llm_providers(self) -> None:
        """Initialize LLM providers for LangChain."""
        logger.info("Initializing LLM providers")
        
        # OpenAI
        if settings.openai_api_key:
            self.llm_providers[LLMProvider.OPENAI.value] = ChatOpenAI(
                api_key=settings.openai_api_key,
                model=settings.default_llm_model,
                temperature=0.1,
                max_tokens=4000
            )
        
        # Anthropic
        if settings.anthropic_api_key:
            self.llm_providers[LLMProvider.ANTHROPIC.value] = ChatAnthropic(
                api_key=settings.anthropic_api_key,
                model="claude-3-opus-20240229",
                temperature=0.1,
                max_tokens=4000
            )
        
        # Google
        if settings.google_api_key:
            self.llm_providers[LLMProvider.GOOGLE.value] = ChatGoogleGenerativeAI(
                google_api_key=settings.google_api_key,
                model="gemini-pro",
                temperature=0.1,
                max_output_tokens=4000
            )
        
        logger.info(f"Initialized {len(self.llm_providers)} LLM providers")
    
    async def _initialize_checkpointer(self) -> None:
        """Initialize the checkpointer for state persistence."""
        checkpoint_dir = Path("./checkpoints")
        checkpoint_dir.mkdir(exist_ok=True)
        
        checkpoint_path = checkpoint_dir / "security_agent.db"
        self.checkpointer = AsyncSqliteSaver.from_conn_string(str(checkpoint_path))
        
        logger.info("Checkpointer initialized", path=str(checkpoint_path))
    
    async def start(self) -> None:
        """Start the orchestrator and begin processing alerts."""
        if self.is_running:
            logger.warning("Orchestrator already running")
            return
        
        logger.info("Starting LangGraph orchestrator")
        self.is_running = True
        
        # Start alert consumer
        asyncio.create_task(self._consume_alerts())
        
        # Start metrics reporter
        asyncio.create_task(self._report_metrics())
        
        logger.info("LangGraph orchestrator started")
    
    async def stop(self) -> None:
        """Stop the orchestrator and cleanup resources."""
        logger.info("Stopping LangGraph orchestrator")
        self.is_running = False
        
        # Disconnect infrastructure
        if "broker" in self.infrastructure:
            await self.infrastructure["broker"].disconnect()
        
        if "graph_db" in self.infrastructure:
            await self.infrastructure["graph_db"].disconnect()
        
        logger.info("LangGraph orchestrator stopped")
    
    async def _consume_alerts(self) -> None:
        """Consume alerts from the message broker."""
        logger.info("Starting alert consumer")
        
        while self.is_running:
            try:
                # Get alerts from broker
                alerts = await self.infrastructure["broker"].consume_alerts(
                    queue_name="security_alerts",
                    batch_size=10
                )
                
                if alerts:
                    # Convert to SecurityAlert objects
                    security_alerts = []
                    for alert_data in alerts:
                        try:
                            alert = SecurityAlert(
                                id=alert_data.get("id", f"alert_{datetime.now().timestamp()}"),
                                timestamp=datetime.fromisoformat(alert_data.get("timestamp", datetime.now().isoformat())),
                                severity=AlertSeverity(alert_data.get("severity", "medium")),
                                type=alert_data.get("type", "unknown"),
                                source=alert_data.get("source", "unknown"),
                                description=alert_data.get("description", ""),
                                details=alert_data.get("details", {}),
                                context=alert_data.get("context", {})
                            )
                            security_alerts.append(alert)
                        except Exception as e:
                            logger.error("Failed to parse alert", error=str(e), alert_data=alert_data)
                    
                    # Process alerts through the graph
                    if security_alerts:
                        await self._process_alerts(security_alerts)
                
                # Small delay between checks
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error("Error in alert consumer", error=str(e), exc_info=True)
                await asyncio.sleep(5)  # Back off on error
    
    async def _process_alerts(self, alerts: List[SecurityAlert]) -> None:
        """Process alerts through the LangGraph."""
        logger.info(f"Processing {len(alerts)} alerts through LangGraph")
        
        # Process alerts in parallel batches
        batch_size = 5
        for i in range(0, len(alerts), batch_size):
            batch = alerts[i:i + batch_size]
            
            # Process batch in parallel
            tasks = []
            for alert in batch:
                task = asyncio.create_task(self.graph.process_alert(alert))
                tasks.append(task)
            
            # Wait for batch to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Log results
            for alert, result in zip(batch, results):
                if isinstance(result, Exception):
                    logger.error("Failed to process alert", 
                               alert_id=alert.id,
                               error=str(result))
                else:
                    logger.info("Alert processed",
                              alert_id=alert.id,
                              status=result.get("status"),
                              metrics=result.get("metrics"))
    
    async def _report_metrics(self) -> None:
        """Periodically report system metrics."""
        while self.is_running:
            try:
                # Collect metrics (this would be more sophisticated in production)
                metrics = {
                    "timestamp": datetime.now().isoformat(),
                    "system": "langgraph_orchestrator",
                    "is_running": self.is_running,
                    "llm_providers": list(self.llm_providers.keys())
                }
                
                logger.info("System metrics", **metrics)
                
                # Report every 60 seconds
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error("Error reporting metrics", error=str(e))
                await asyncio.sleep(60)
    
    async def process_manual_alert(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a manually submitted alert."""
        try:
            # Create SecurityAlert object
            alert = SecurityAlert(
                id=alert_data.get("id", f"manual_{datetime.now().timestamp()}"),
                timestamp=datetime.now(),
                severity=AlertSeverity(alert_data.get("severity", "medium")),
                type=alert_data.get("type", "manual"),
                source=alert_data.get("source", "manual_submission"),
                description=alert_data.get("description", ""),
                details=alert_data.get("details", {}),
                context=alert_data.get("context", {})
            )
            
            # Process through graph
            result = await self.graph.process_alert(alert)
            
            return result
            
        except Exception as e:
            logger.error("Failed to process manual alert", error=str(e), exc_info=True)
            raise