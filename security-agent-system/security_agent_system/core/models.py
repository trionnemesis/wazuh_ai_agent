"""安全代理系統的核心資料模型。"""
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator
import uuid


class TaskStatus(str, Enum):
    """任務生命週期狀態。"""
    PENDING = "PENDING"
    HUNTING = "HUNTING"
    AWAITING_EXECUTION = "AWAITING_EXECUTION"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AlertSeverity(str, Enum):
    """警報嚴重性等級。"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ThreatCategory(str, Enum):
    """威脅分類。"""
    MALWARE = "MALWARE"
    INTRUSION = "INTRUSION"
    DATA_EXFILTRATION = "DATA_EXFILTRATION"
    PRIVILEGE_ESCALATION = "PRIVILEGE_ESCALATION"
    LATERAL_MOVEMENT = "LATERAL_MOVEMENT"
    COMMAND_AND_CONTROL = "COMMAND_AND_CONTROL"
    UNKNOWN = "UNKNOWN"


class ActionType(str, Enum):
    """可用的回應動作。"""
    ISOLATE_HOST = "ISOLATE_HOST"
    BLOCK_IP = "BLOCK_IP"
    DISABLE_USER = "DISABLE_USER"
    QUARANTINE_FILE = "QUARANTINE_FILE"
    CREATE_TICKET = "CREATE_TICKET"
    SEND_NOTIFICATION = "SEND_NOTIFICATION"
    CUSTOM_SCRIPT = "CUSTOM_SCRIPT"


class Task(BaseModel):
    """在系統中流動的核心任務模型。"""
    
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # 警報資訊
    alert_id: str
    alert_source: str  # 例如："wazuh", "siem", "edr"
    alert_timestamp: datetime
    severity: AlertSeverity
    
    # 處理元資料
    assigned_to: Optional[str] = None
    processing_start: Optional[datetime] = None
    processing_end: Optional[datetime] = None
    retry_count: int = 0
    
    # 錯誤追蹤
    error_message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    
    @validator("updated_at", always=True)
    def update_timestamp(cls, v):
        """自動更新時間戳。"""
        return datetime.utcnow()


class AlertMessage(BaseModel):
    """傳送給管理代理的初始警報的訊息格式。"""
    
    alert_id: str
    source: str
    timestamp: datetime
    severity: AlertSeverity
    
    # 警報詳細資訊
    title: str
    description: str
    raw_data: Dict[str, Any]
    
    # 上下文資訊
    affected_assets: List[str] = []
    source_ips: List[str] = []
    destination_ips: List[str] = []
    user_accounts: List[str] = []
    file_hashes: List[str] = []
    
    # 初始分類
    suspected_category: Optional[ThreatCategory] = None
    confidence_score: Optional[float] = None


class GraphContext(BaseModel):
    """來自 GraphRAG 的基於圖形的上下文。"""
    
    # 實體關係
    entities: List[Dict[str, Any]] = []
    relationships: List[Dict[str, Any]] = []
    
    # 攻擊路徑分析
    attack_paths: List[List[str]] = []
    risk_score: float = 0.0
    
    # 歷史上下文
    similar_incidents: List[str] = []
    related_campaigns: List[str] = []
    
    # 威脅情報
    iocs: List[Dict[str, Any]] = []
    ttps: List[str] = []  # MITRE ATT&CK TTPs


class VectorContext(BaseModel):
    """向量搜索結果和相似警報。"""
    
    similar_alerts: List[Dict[str, Any]] = []
    similarity_scores: List[float] = []
    
    # 模式分析
    detected_patterns: List[str] = []
    anomaly_score: float = 0.0
    
    # 歷史統計資料
    occurrence_count: int = 0
    last_seen: Optional[datetime] = None
    resolution_history: List[Dict[str, Any]] = []


class ThreatProfile(BaseModel):
    """由獵人代理產生的全面威脅分析。"""
    
    task_id: str
    profile_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # 原始警報
    alert: AlertMessage
    
    # 豐富後的上下文
    graph_context: GraphContext
    vector_context: VectorContext
    
    # 資產資訊
    asset_criticality: Dict[str, float] = {}
    asset_vulnerabilities: Dict[str, List[str]] = {}
    
    # 威脅評估
    threat_category: ThreatCategory
    threat_actor: Optional[str] = None
    campaign_id: Optional[str] = None
    
    # 風險分析
    overall_risk_score: float
    impact_assessment: Dict[str, Any] = {}
    likelihood_assessment: float = 0.0
    
    # 建議動作
    recommended_actions: List[Dict[str, Any]] = []
    priority_score: float = 0.0


class HuntingMessage(BaseModel):
    """從管理代理傳送給獵人代理的訊息。"""
    
    task: Task
    alert: AlertMessage
    
    # 狩獵參數
    max_depth: int = 3  # 圖形遍歷深度
    time_window_hours: int = 24  # 歷史搜索窗口
    include_threat_intel: bool = True
    
    # 效能提示
    priority: str = "normal"  # low, normal, high, critical
    timeout_seconds: int = 300


class RecommendedAction(BaseModel):
    """結構化的動作建議。"""
    
    action_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action_type: ActionType
    priority: int  # 1 (最高) 到 5 (最低)
    
    # 動作詳細資訊
    description: str
    parameters: Dict[str, Any]
    
    # 風險評估
    risk_level: str  # low, medium, high
    potential_impact: str
    rollback_available: bool = False
    
    # 自動化支援
    automation_ready: bool = True
    requires_approval: bool = True
    estimated_duration_seconds: int = 60


class ExecutionReport(BaseModel):
    """由執行者代理產生的最終分析報告。"""
    
    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # 高階主管摘要
    executive_summary: str
    threat_narrative: str
    
    # 詳細分析
    technical_details: Dict[str, Any]
    ioc_summary: List[Dict[str, Any]]
    timeline: List[Dict[str, Any]]
    
    # 建議
    recommended_actions: List[RecommendedAction]
    
    # 信賴度指標
    analysis_confidence: float
    false_positive_probability: float
    
    # 支援證據
    evidence: List[Dict[str, Any]] = []
    references: List[str] = []


class ExecutionMessage(BaseModel):
    """從獵人代理傳送給執行者代理的訊息。"""
    
    task: Task
    threat_profile: ThreatProfile
    
    # 執行參數
    auto_execute_low_risk: bool = False
    notification_channels: List[str] = ["slack"]
    
    # 分析提示
    analysis_depth: str = "comprehensive"  # quick, standard, comprehensive
    include_recommendations: bool = True
    generate_timeline: bool = True


class ApprovalRequest(BaseModel):
    """人類批准請求。"""
    
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    requested_at: datetime = Field(default_factory=datetime.utcnow)
    
    # 請求詳細資訊
    execution_report: ExecutionReport
    requested_actions: List[RecommendedAction]
    
    # 批准元資料
    approver: Optional[str] = None
    approved: Optional[bool] = None
    approval_timestamp: Optional[datetime] = None
    approval_comments: Optional[str] = None
    
    # 逾時設定
    timeout_minutes: int = 30
    escalation_contacts: List[str] = []


class ExecutionResult(BaseModel):
    """動作執行的結果。"""
    
    result_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action_id: str
    task_id: str
    executed_at: datetime = Field(default_factory=datetime.utcnow)
    
    # 執行狀態
    success: bool
    execution_time_seconds: float
    
    # 結果
    output: Dict[str, Any] = {}
    error_message: Optional[str] = None
    
    # 稽核軌跡
    executed_by: str
    approval_id: Optional[str] = None
    rollback_id: Optional[str] = None