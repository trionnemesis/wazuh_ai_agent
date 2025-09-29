"""Core data models for the Security Agent System."""
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator
import uuid


class TaskStatus(str, Enum):
    """Task lifecycle states."""
    PENDING = "PENDING"
    HUNTING = "HUNTING"
    AWAITING_EXECUTION = "AWAITING_EXECUTION"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ThreatCategory(str, Enum):
    """Threat categorization."""
    MALWARE = "MALWARE"
    INTRUSION = "INTRUSION"
    DATA_EXFILTRATION = "DATA_EXFILTRATION"
    PRIVILEGE_ESCALATION = "PRIVILEGE_ESCALATION"
    LATERAL_MOVEMENT = "LATERAL_MOVEMENT"
    COMMAND_AND_CONTROL = "COMMAND_AND_CONTROL"
    UNKNOWN = "UNKNOWN"


class ActionType(str, Enum):
    """Available response actions."""
    ISOLATE_HOST = "ISOLATE_HOST"
    BLOCK_IP = "BLOCK_IP"
    DISABLE_USER = "DISABLE_USER"
    QUARANTINE_FILE = "QUARANTINE_FILE"
    CREATE_TICKET = "CREATE_TICKET"
    SEND_NOTIFICATION = "SEND_NOTIFICATION"
    CUSTOM_SCRIPT = "CUSTOM_SCRIPT"


class Task(BaseModel):
    """Core task model that flows through the system."""
    
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Alert Information
    alert_id: str
    alert_source: str  # e.g., "wazuh", "siem", "edr"
    alert_timestamp: datetime
    severity: AlertSeverity
    
    # Processing Metadata
    assigned_to: Optional[str] = None
    processing_start: Optional[datetime] = None
    processing_end: Optional[datetime] = None
    retry_count: int = 0
    
    # Error Tracking
    error_message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    
    @validator("updated_at", always=True)
    def update_timestamp(cls, v):
        """Auto-update timestamp."""
        return datetime.utcnow()


class AlertMessage(BaseModel):
    """Message format for initial alerts sent to Manager Agent."""
    
    alert_id: str
    source: str
    timestamp: datetime
    severity: AlertSeverity
    
    # Alert Details
    title: str
    description: str
    raw_data: Dict[str, Any]
    
    # Context Information
    affected_assets: List[str] = []
    source_ips: List[str] = []
    destination_ips: List[str] = []
    user_accounts: List[str] = []
    file_hashes: List[str] = []
    
    # Initial Classification
    suspected_category: Optional[ThreatCategory] = None
    confidence_score: Optional[float] = None


class GraphContext(BaseModel):
    """Graph-based context from GraphRAG."""
    
    # Entity Relationships
    entities: List[Dict[str, Any]] = []
    relationships: List[Dict[str, Any]] = []
    
    # Attack Path Analysis
    attack_paths: List[List[str]] = []
    risk_score: float = 0.0
    
    # Historical Context
    similar_incidents: List[str] = []
    related_campaigns: List[str] = []
    
    # Threat Intelligence
    iocs: List[Dict[str, Any]] = []
    ttps: List[str] = []  # MITRE ATT&CK TTPs


class VectorContext(BaseModel):
    """Vector search results and similar alerts."""
    
    similar_alerts: List[Dict[str, Any]] = []
    similarity_scores: List[float] = []
    
    # Pattern Analysis
    detected_patterns: List[str] = []
    anomaly_score: float = 0.0
    
    # Historical Statistics
    occurrence_count: int = 0
    last_seen: Optional[datetime] = None
    resolution_history: List[Dict[str, Any]] = []


class ThreatProfile(BaseModel):
    """Comprehensive threat analysis produced by Hunter Agent."""
    
    task_id: str
    profile_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Original Alert
    alert: AlertMessage
    
    # Enriched Context
    graph_context: GraphContext
    vector_context: VectorContext
    
    # Asset Information
    asset_criticality: Dict[str, float] = {}
    asset_vulnerabilities: Dict[str, List[str]] = {}
    
    # Threat Assessment
    threat_category: ThreatCategory
    threat_actor: Optional[str] = None
    campaign_id: Optional[str] = None
    
    # Risk Analysis
    overall_risk_score: float
    impact_assessment: Dict[str, Any] = {}
    likelihood_assessment: float = 0.0
    
    # Recommended Actions
    recommended_actions: List[Dict[str, Any]] = []
    priority_score: float = 0.0


class HuntingMessage(BaseModel):
    """Message sent from Manager to Hunter Agent."""
    
    task: Task
    alert: AlertMessage
    
    # Hunting Parameters
    max_depth: int = 3  # Graph traversal depth
    time_window_hours: int = 24  # Historical search window
    include_threat_intel: bool = True
    
    # Performance Hints
    priority: str = "normal"  # low, normal, high, critical
    timeout_seconds: int = 300


class RecommendedAction(BaseModel):
    """Structured action recommendation."""
    
    action_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action_type: ActionType
    priority: int  # 1 (highest) to 5 (lowest)
    
    # Action Details
    description: str
    parameters: Dict[str, Any]
    
    # Risk Assessment
    risk_level: str  # low, medium, high
    potential_impact: str
    rollback_available: bool = False
    
    # Automation Support
    automation_ready: bool = True
    requires_approval: bool = True
    estimated_duration_seconds: int = 60


class ExecutionReport(BaseModel):
    """Final analysis report generated by Executor Agent."""
    
    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Executive Summary
    executive_summary: str
    threat_narrative: str
    
    # Detailed Analysis
    technical_details: Dict[str, Any]
    ioc_summary: List[Dict[str, Any]]
    timeline: List[Dict[str, Any]]
    
    # Recommendations
    recommended_actions: List[RecommendedAction]
    
    # Confidence Metrics
    analysis_confidence: float
    false_positive_probability: float
    
    # Supporting Evidence
    evidence: List[Dict[str, Any]] = []
    references: List[str] = []


class ExecutionMessage(BaseModel):
    """Message sent from Hunter to Executor Agent."""
    
    task: Task
    threat_profile: ThreatProfile
    
    # Execution Parameters
    auto_execute_low_risk: bool = False
    notification_channels: List[str] = ["slack"]
    
    # Analysis Hints
    analysis_depth: str = "comprehensive"  # quick, standard, comprehensive
    include_recommendations: bool = True
    generate_timeline: bool = True


class ApprovalRequest(BaseModel):
    """Human approval request."""
    
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    requested_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Request Details
    execution_report: ExecutionReport
    requested_actions: List[RecommendedAction]
    
    # Approval Metadata
    approver: Optional[str] = None
    approved: Optional[bool] = None
    approval_timestamp: Optional[datetime] = None
    approval_comments: Optional[str] = None
    
    # Timeout Configuration
    timeout_minutes: int = 30
    escalation_contacts: List[str] = []


class ExecutionResult(BaseModel):
    """Result of action execution."""
    
    result_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action_id: str
    task_id: str
    executed_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Execution Status
    success: bool
    execution_time_seconds: float
    
    # Results
    output: Dict[str, Any] = {}
    error_message: Optional[str] = None
    
    # Audit Trail
    executed_by: str
    approval_id: Optional[str] = None
    rollback_id: Optional[str] = None
