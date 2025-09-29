"""State definitions for LangGraph agents."""
from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class SecurityAlert(BaseModel):
    """Security alert model."""
    id: str
    timestamp: datetime
    severity: AlertSeverity
    type: str
    source: str
    description: str
    details: Dict[str, Any] = Field(default_factory=dict)
    context: Dict[str, Any] = Field(default_factory=dict)
    investigation_status: str = "pending"
    remediation_status: str = "pending"


class Investigation(BaseModel):
    """Investigation results from Hunter agent."""
    alert_id: str
    findings: List[Dict[str, Any]]
    risk_score: float
    affected_assets: List[str]
    attack_indicators: List[str]
    recommendations: List[str]
    evidence: Dict[str, Any] = Field(default_factory=dict)


class RemediationPlan(BaseModel):
    """Remediation plan from Manager agent."""
    alert_id: str
    priority: int
    actions: List[Dict[str, Any]]
    estimated_impact: str
    rollback_plan: Optional[Dict[str, Any]] = None
    approval_required: bool = False


class ExecutionResult(BaseModel):
    """Execution result from Executor agent."""
    alert_id: str
    action_id: str
    status: str
    result: Dict[str, Any]
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class AgentState(TypedDict):
    """Shared state for all agents in the graph."""
    # Current alert being processed
    current_alert: Optional[SecurityAlert]
    
    # Alert queue
    alert_queue: List[SecurityAlert]
    
    # Investigation results
    investigations: Dict[str, Investigation]
    
    # Remediation plans
    remediation_plans: Dict[str, RemediationPlan]
    
    # Execution results
    execution_results: List[ExecutionResult]
    
    # Agent metadata
    agent_status: Dict[str, str]
    
    # Workflow state
    workflow_step: str
    workflow_history: List[Dict[str, Any]]
    
    # Error tracking
    errors: List[Dict[str, Any]]
    
    # Performance metrics
    metrics: Dict[str, Any]
    
    # Configuration
    config: Dict[str, Any]
    
    # Message history for LCEL chains
    messages: List[Dict[str, Any]]
    
    # Decision tracking
    decisions: List[Dict[str, Any]]
    
    # Context from external systems
    external_context: Dict[str, Any]