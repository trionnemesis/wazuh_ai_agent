"""核心介面與抽象基底類別。"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable, Awaitable
from datetime import datetime
import asyncio

from .models import (
    Task, TaskStatus, AlertMessage, HuntingMessage, 
    ExecutionMessage, ThreatProfile, ExecutionReport
)


class IMessageBroker(ABC):
    """訊息代理實作的介面。"""
    
    @abstractmethod
    async def connect(self) -> None:
        """建立與訊息代理的連線。"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """關閉與訊息代理的連線。"""
        pass
    
    @abstractmethod
    async def publish(self, queue: str, message: Dict[str, Any]) -> None:
        """將訊息發布到佇列。"""
        pass
    
    @abstractmethod
    async def subscribe(
        self, 
        queue: str, 
        handler: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """使用訊息處理常式訂閱佇列。"""
        pass
    
    @abstractmethod
    async def acknowledge(self, message_id: str) -> None:
        """確認訊息成功處理。"""
        pass
    
    @abstractmethod
    async def reject(self, message_id: str, requeue: bool = False) -> None:
        """拒絕訊息，可選擇性地重新排入佇列。"""
        pass


class IAgent(ABC):
    """系統中所有代理的基礎介面。"""
    
    @property
    @abstractmethod
    def agent_id(self) -> str:
        """代理的唯一識別碼。"""
        pass
    
    @property
    @abstractmethod
    def agent_type(self) -> str:
        """代理的類型 (manager, hunter, executor)。"""
        pass
    
    @abstractmethod
    async def initialize(self) -> None:
        """初始化代理及其資源。"""
        pass
    
    @abstractmethod
    async def start(self) -> None:
        """啟動代理的主要處理迴圈。"""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """優雅地停止代理。"""
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """返回代理的健康狀態。"""
        pass


class IManagerAgent(IAgent):
    """管理代理的介面。"""
    
    @abstractmethod
    async def process_alert(self, alert: AlertMessage) -> Task:
        """處理傳入的警報並建立任務。"""
        pass
    
    @abstractmethod
    async def classify_alert(self, alert: AlertMessage) -> Dict[str, Any]:
        """對警報進行分類以進行路由決策。"""
        pass
    
    @abstractmethod
    async def deduplicate_alert(self, alert: AlertMessage) -> Optional[str]:
        """檢查警報是否重複，如果找到則返回現有的 task_id。"""
        pass
    
    @abstractmethod
    async def track_task_status(self, task_id: str, status: TaskStatus) -> None:
        """在追蹤系統中更新任務狀態。"""
        pass


class IHunterAgent(IAgent):
    """獵人代理的介面。"""
    
    @abstractmethod
    async def hunt_threat(self, message: HuntingMessage) -> ThreatProfile:
        """執行威脅狩獵和豐富化。"""
        pass
    
    @abstractmethod
    async def query_graph(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """查詢 GraphRAG 以獲取實體關係。"""
        pass
    
    @abstractmethod
    async def search_vectors(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """在向量資料庫中搜索相似的警報。"""
        pass
    
    @abstractmethod
    async def enrich_context(self, alert: AlertMessage) -> Dict[str, Any]:
        """用額外的上下文豐富警報。"""
        pass


class IExecutorAgent(IAgent):
    """執行者代理的介面。"""
    
    @abstractmethod
    async def analyze_threat(self, message: ExecutionMessage) -> ExecutionReport:
        """執行最終的威脅分析。"""
        pass
    
    @abstractmethod
    async def generate_recommendations(
        self, 
        threat_profile: ThreatProfile
    ) -> List[Dict[str, Any]]:
        """產生行動建議。"""
        pass
    
    @abstractmethod
    async def request_approval(self, report: ExecutionReport) -> bool:
        """請求人類批准行動。"""
        pass
    
    @abstractmethod
    async def execute_action(
        self, 
        action: Dict[str, Any], 
        approval_id: str
    ) -> Dict[str, Any]:
        """執行已批准的行動。"""
        pass


class ILLMProvider(ABC):
    """LLM 供應商的介面。"""
    
    @abstractmethod
    async def generate(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000
    ) -> str:
        """從 LLM 產生回應。"""
        pass
    
    @abstractmethod
    async def embed(self, text: str) -> List[float]:
        """為文字產生嵌入。"""
        pass


class IGraphDatabase(ABC):
    """圖形資料庫操作的介面。"""
    
    @abstractmethod
    async def connect(self) -> None:
        """連接到圖形資料庫。"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """從圖形資料庫斷開連接。"""
        pass
    
    @abstractmethod
    async def create_node(
        self, 
        node_type: str, 
        properties: Dict[str, Any]
    ) -> str:
        """在圖形中建立一個節點。"""
        pass
    
    @abstractmethod
    async def create_relationship(
        self, 
        source_id: str, 
        target_id: str, 
        relationship_type: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> str:
        """在節點之間建立關係。"""
        pass
    
    @abstractmethod
    async def find_paths(
        self, 
        start_node: str, 
        end_node: Optional[str] = None,
        max_depth: int = 3
    ) -> List[List[Dict[str, Any]]]:
        """在圖形中尋找路徑。"""
        pass
    
    @abstractmethod
    async def query(self, cypher: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """執行一個 Cypher 查詢。"""
        pass


class IVectorDatabase(ABC):
    """向量資料庫操作的介面。"""
    
    @abstractmethod
    async def connect(self) -> None:
        """連接到向量資料庫。"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """從向量資料庫斷開連接。"""
        pass
    
    @abstractmethod
    async def insert(
        self, 
        vector: List[float], 
        metadata: Dict[str, Any],
        collection: str = "alerts"
    ) -> str:
        """插入帶有元資料的向量。"""
        pass
    
    @abstractmethod
    async def search(
        self, 
        vector: List[float], 
        top_k: int = 10,
        collection: str = "alerts",
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """搜索相似的向量。"""
        pass
    
    @abstractmethod
    async def delete(self, vector_id: str, collection: str = "alerts") -> bool:
        """按 ID 刪除向量。"""
        pass


class INotificationService(ABC):
    """通知服務的介面。"""
    
    @abstractmethod
    async def send_alert(
        self, 
        title: str, 
        message: str,
        severity: str,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """發送警報通知。"""
        pass
    
    @abstractmethod
    async def request_approval(
        self, 
        title: str, 
        message: str,
        actions: List[Dict[str, Any]],
        callback_url: str
    ) -> str:
        """帶有回呼的請求批准。"""
        pass
    
    @abstractmethod
    async def send_report(
        self, 
        report: ExecutionReport,
        recipients: List[str]
    ) -> bool:
        """發送執行報告。"""
        pass


class IActionExecutor(ABC):
    """行動執行服務的介面。"""
    
    @abstractmethod
    async def execute(
        self, 
        action_type: str, 
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """執行一個安全行動。"""
        pass
    
    @abstractmethod
    async def validate_action(
        self, 
        action_type: str, 
        parameters: Dict[str, Any]
    ) -> bool:
        """在執行前驗證行動。"""
        pass
    
    @abstractmethod
    async def rollback(
        self, 
        action_id: str
    ) -> bool:
        """回滾先前執行的行動。"""
        pass