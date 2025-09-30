"""LangGraph 代理的狀態定義。"""
from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class AlertSeverity(str, Enum):
    """警報嚴重性等級。"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class SecurityAlert(BaseModel):
    """安全警報模型。"""
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
    """來自獵人代理的調查結果。"""
    alert_id: str
    findings: List[Dict[str, Any]]
    risk_score: float
    affected_assets: List[str]
    attack_indicators: List[str]
    recommendations: List[str]
    evidence: Dict[str, Any] = Field(default_factory=dict)


class RemediationPlan(BaseModel):
    """來自管理代理的修復計畫。"""
    alert_id: str
    priority: int
    actions: List[Dict[str, Any]]
    estimated_impact: str
    rollback_plan: Optional[Dict[str, Any]] = None
    approval_required: bool = False


class ExecutionResult(BaseModel):
    """來自執行者代理的執行結果。"""
    alert_id: str
    action_id: str
    status: str
    result: Dict[str, Any]
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class AgentState(TypedDict):
    """圖中所有代理的共享狀態。"""
    # 正在處理的目前警報
    current_alert: Optional[SecurityAlert]
    
    # 警報佇列
    alert_queue: List[SecurityAlert]
    
    # 調查結果
    investigations: Dict[str, Investigation]
    
    # 修復計畫
    remediation_plans: Dict[str, RemediationPlan]
    
    # 執行結果
    execution_results: List[ExecutionResult]
    
    # 代理元資料
    agent_status: Dict[str, str]
    
    # 工作流程狀態
    workflow_step: str
    workflow_history: List[Dict[str, Any]]
    
    # 錯誤追蹤
    errors: List[Dict[str, Any]]
    
    # 效能指標
    metrics: Dict[str, Any]
    
    # 設定
    config: Dict[str, Any]
    
    # LCEL 鏈的訊息歷史記錄
    messages: List[Dict[str, Any]]
    
    # 決策追蹤
    decisions: List[Dict[str, Any]]
    
    # 來自外部系統的上下文
    external_context: Dict[str, Any]