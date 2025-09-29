"""Core interfaces and abstract base classes."""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable, Awaitable
from datetime import datetime
import asyncio

from .models import (
    Task, TaskStatus, AlertMessage, HuntingMessage, 
    ExecutionMessage, ThreatProfile, ExecutionReport
)


class IMessageBroker(ABC):
    """Interface for message broker implementations."""
    
    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the message broker."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection to the message broker."""
        pass
    
    @abstractmethod
    async def publish(self, queue: str, message: Dict[str, Any]) -> None:
        """Publish a message to a queue."""
        pass
    
    @abstractmethod
    async def subscribe(
        self, 
        queue: str, 
        handler: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """Subscribe to a queue with a message handler."""
        pass
    
    @abstractmethod
    async def acknowledge(self, message_id: str) -> None:
        """Acknowledge successful message processing."""
        pass
    
    @abstractmethod
    async def reject(self, message_id: str, requeue: bool = False) -> None:
        """Reject a message, optionally requeuing it."""
        pass


class IAgent(ABC):
    """Base interface for all agents in the system."""
    
    @property
    @abstractmethod
    def agent_id(self) -> str:
        """Unique identifier for the agent."""
        pass
    
    @property
    @abstractmethod
    def agent_type(self) -> str:
        """Type of agent (manager, hunter, executor)."""
        pass
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the agent and its resources."""
        pass
    
    @abstractmethod
    async def start(self) -> None:
        """Start the agent's main processing loop."""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """Gracefully stop the agent."""
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Return agent health status."""
        pass


class IManagerAgent(IAgent):
    """Interface for Manager Agent."""
    
    @abstractmethod
    async def process_alert(self, alert: AlertMessage) -> Task:
        """Process incoming alert and create task."""
        pass
    
    @abstractmethod
    async def classify_alert(self, alert: AlertMessage) -> Dict[str, Any]:
        """Classify alert for routing decisions."""
        pass
    
    @abstractmethod
    async def deduplicate_alert(self, alert: AlertMessage) -> Optional[str]:
        """Check if alert is duplicate, return existing task_id if found."""
        pass
    
    @abstractmethod
    async def track_task_status(self, task_id: str, status: TaskStatus) -> None:
        """Update task status in tracking system."""
        pass


class IHunterAgent(IAgent):
    """Interface for Hunter Agent."""
    
    @abstractmethod
    async def hunt_threat(self, message: HuntingMessage) -> ThreatProfile:
        """Perform threat hunting and enrichment."""
        pass
    
    @abstractmethod
    async def query_graph(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Query GraphRAG for entity relationships."""
        pass
    
    @abstractmethod
    async def search_vectors(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Search vector database for similar alerts."""
        pass
    
    @abstractmethod
    async def enrich_context(self, alert: AlertMessage) -> Dict[str, Any]:
        """Enrich alert with additional context."""
        pass


class IExecutorAgent(IAgent):
    """Interface for Executor Agent."""
    
    @abstractmethod
    async def analyze_threat(self, message: ExecutionMessage) -> ExecutionReport:
        """Perform final threat analysis."""
        pass
    
    @abstractmethod
    async def generate_recommendations(
        self, 
        threat_profile: ThreatProfile
    ) -> List[Dict[str, Any]]:
        """Generate action recommendations."""
        pass
    
    @abstractmethod
    async def request_approval(self, report: ExecutionReport) -> bool:
        """Request human approval for actions."""
        pass
    
    @abstractmethod
    async def execute_action(
        self, 
        action: Dict[str, Any], 
        approval_id: str
    ) -> Dict[str, Any]:
        """Execute approved action."""
        pass


class ILLMProvider(ABC):
    """Interface for LLM providers."""
    
    @abstractmethod
    async def generate(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000
    ) -> str:
        """Generate response from LLM."""
        pass
    
    @abstractmethod
    async def embed(self, text: str) -> List[float]:
        """Generate embedding for text."""
        pass


class IGraphDatabase(ABC):
    """Interface for graph database operations."""
    
    @abstractmethod
    async def connect(self) -> None:
        """Connect to graph database."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from graph database."""
        pass
    
    @abstractmethod
    async def create_node(
        self, 
        node_type: str, 
        properties: Dict[str, Any]
    ) -> str:
        """Create a node in the graph."""
        pass
    
    @abstractmethod
    async def create_relationship(
        self, 
        source_id: str, 
        target_id: str, 
        relationship_type: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a relationship between nodes."""
        pass
    
    @abstractmethod
    async def find_paths(
        self, 
        start_node: str, 
        end_node: Optional[str] = None,
        max_depth: int = 3
    ) -> List[List[Dict[str, Any]]]:
        """Find paths in the graph."""
        pass
    
    @abstractmethod
    async def query(self, cypher: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a Cypher query."""
        pass


class IVectorDatabase(ABC):
    """Interface for vector database operations."""
    
    @abstractmethod
    async def connect(self) -> None:
        """Connect to vector database."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from vector database."""
        pass
    
    @abstractmethod
    async def insert(
        self, 
        vector: List[float], 
        metadata: Dict[str, Any],
        collection: str = "alerts"
    ) -> str:
        """Insert vector with metadata."""
        pass
    
    @abstractmethod
    async def search(
        self, 
        vector: List[float], 
        top_k: int = 10,
        collection: str = "alerts",
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar vectors."""
        pass
    
    @abstractmethod
    async def delete(self, vector_id: str, collection: str = "alerts") -> bool:
        """Delete a vector by ID."""
        pass


class INotificationService(ABC):
    """Interface for notification services."""
    
    @abstractmethod
    async def send_alert(
        self, 
        title: str, 
        message: str,
        severity: str,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """Send an alert notification."""
        pass
    
    @abstractmethod
    async def request_approval(
        self, 
        title: str, 
        message: str,
        actions: List[Dict[str, Any]],
        callback_url: str
    ) -> str:
        """Request approval with callback."""
        pass
    
    @abstractmethod
    async def send_report(
        self, 
        report: ExecutionReport,
        recipients: List[str]
    ) -> bool:
        """Send execution report."""
        pass


class IActionExecutor(ABC):
    """Interface for action execution services."""
    
    @abstractmethod
    async def execute(
        self, 
        action_type: str, 
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a security action."""
        pass
    
    @abstractmethod
    async def validate_action(
        self, 
        action_type: str, 
        parameters: Dict[str, Any]
    ) -> bool:
        """Validate action before execution."""
        pass
    
    @abstractmethod
    async def rollback(
        self, 
        action_id: str
    ) -> bool:
        """Rollback a previously executed action."""
        pass
