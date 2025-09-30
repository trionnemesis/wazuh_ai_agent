"""基於 LangGraph 的安全代理系統協調器。"""
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
from ...core.config import settings, LLMProvider
from ...infrastructure import (
    RabbitMQBroker, KafkaBroker,
    Neo4jDatabase, ChromaDatabase,
    SlackNotificationService
)
from ...services.action_executor import ActionExecutorService

logger = structlog.get_logger()


class LangGraphOrchestrator:
    """協調基於 LangGraph 的安全代理系統。"""
    
    def __init__(self):
        """初始化 LangGraph 協調器。"""
        self.graph: Optional[SecurityAgentGraph] = None
        self.infrastructure: Dict[str, Any] = {}
        self.llm_providers: Dict[str, Any] = {}
        self.checkpointer: Optional[AsyncSqliteSaver] = None
        self.is_running = False
        
    async def initialize(self) -> None:
        """初始化所有系統元件。"""
        logger.info("正在初始化 LangGraph 安全代理系統")
        
        try:
            # 初始化基礎設施
            await self._initialize_infrastructure()
            
            # 初始化 LLM 供應商
            await self._initialize_llm_providers()
            
            # 初始化用於狀態持久化的檢查點
            await self._initialize_checkpointer()
            
            # 建立代理節點
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
            
            # 建立圖
            self.graph = SecurityAgentGraph(
                manager_node=manager_node,
                hunter_node=hunter_node,
                executor_node=executor_node,
                checkpointer=self.checkpointer
            )
            
            logger.info("LangGraph 系統初始化完成")
            
        except Exception as e:
            logger.error("初始化 LangGraph 系統失敗", error=str(e), exc_info=True)
            raise
    
    async def _initialize_infrastructure(self) -> None:
        """初始化基礎設施元件。"""
        logger.info("正在初始化基礎設施元件")
        
        # 訊息代理
        if settings.broker_type == "rabbitmq":
            self.infrastructure["broker"] = RabbitMQBroker()
        else:
            self.infrastructure["broker"] = KafkaBroker()
        
        # 初始化代理連線
        await self.infrastructure["broker"].connect()
        
        # 圖形資料庫
        self.infrastructure["graph_db"] = Neo4jDatabase()
        await self.infrastructure["graph_db"].connect()
        
        # 向量資料庫
        self.infrastructure["vector_db"] = ChromaDatabase()
        await self.infrastructure["vector_db"].initialize()
        
        # 通知服務
        self.infrastructure["notifier"] = SlackNotificationService()
        
        # 行動執行器
        self.infrastructure["action_executor"] = ActionExecutorService()
        
        logger.info("基礎設施元件已初始化")
    
    async def _initialize_llm_providers(self) -> None:
        """為 LangChain 初始化 LLM 供應商。"""
        logger.info("正在初始化 LLM 供應商")
        
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
        
        logger.info(f"已初始化 {len(self.llm_providers)} 個 LLM 供應商")
    
    async def _initialize_checkpointer(self) -> None:
        """初始化用於狀態持久化的檢查點。"""
        checkpoint_dir = Path("./checkpoints")
        checkpoint_dir.mkdir(exist_ok=True)
        
        checkpoint_path = checkpoint_dir / "security_agent.db"
        self.checkpointer = AsyncSqliteSaver.from_conn_string(str(checkpoint_path))
        
        logger.info("檢查點已初始化", path=str(checkpoint_path))
    
    async def start(self) -> None:
        """啟動協調器並開始處理警報。"""
        if self.is_running:
            logger.warning("協調器已在執行中")
            return
        
        logger.info("正在啟動 LangGraph 協調器")
        self.is_running = True
        
        # 啟動警報消費者
        asyncio.create_task(self._consume_alerts())
        
        # 啟動指標回報器
        asyncio.create_task(self._report_metrics())
        
        logger.info("LangGraph 協調器已啟動")
    
    async def stop(self) -> None:
        """停止協調器並清理資源。"""
        logger.info("正在停止 LangGraph 協調器")
        self.is_running = False
        
        # 中斷基礎設施連線
        if "broker" in self.infrastructure:
            await self.infrastructure["broker"].disconnect()
        
        if "graph_db" in self.infrastructure:
            await self.infrastructure["graph_db"].disconnect()
        
        logger.info("LangGraph 協調器已停止")
    
    async def _consume_alerts(self) -> None:
        """從訊息代理消費警報。"""
        logger.info("正在啟動警報消費者")
        
        while self.is_running:
            try:
                # 從代理獲取警報
                alerts = await self.infrastructure["broker"].consume_alerts(
                    queue_name="security_alerts",
                    batch_size=10
                )
                
                if alerts:
                    # 轉換為 SecurityAlert 物件
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
                            logger.error("解析警報失敗", error=str(e), alert_data=alert_data)
                    
                    # 透過圖處理警報
                    if security_alerts:
                        await self._process_alerts(security_alerts)
                
                # 檢查之間的小延遲
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error("警報消費者發生錯誤", error=str(e), exc_info=True)
                await asyncio.sleep(5)  # 發生錯誤時退避
    
    async def _process_alerts(self, alerts: List[SecurityAlert]) -> None:
        """透過 LangGraph 處理警報。"""
        logger.info(f"正在透過 LangGraph 處理 {len(alerts)} 則警報")
        
        # 平行批次處理警報
        batch_size = 5
        for i in range(0, len(alerts), batch_size):
            batch = alerts[i:i + batch_size]
            
            # 平行處理批次
            tasks = []
            for alert in batch:
                task = asyncio.create_task(self.graph.process_alert(alert))
                tasks.append(task)
            
            # 等待批次完成
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 記錄結果
            for alert, result in zip(batch, results):
                if isinstance(result, Exception):
                    logger.error("處理警報失敗",
                               alert_id=alert.id,
                               error=str(result))
                else:
                    logger.info("警報已處理",
                              alert_id=alert.id,
                              status=result.get("status"),
                              metrics=result.get("metrics"))
    
    async def _report_metrics(self) -> None:
        """定期回報系統指標。"""
        while self.is_running:
            try:
                # 收集指標 (這在生產環境中會更複雜)
                metrics = {
                    "timestamp": datetime.now().isoformat(),
                    "system": "langgraph_orchestrator",
                    "is_running": self.is_running,
                    "llm_providers": list(self.llm_providers.keys())
                }
                
                logger.info("系統指標", **metrics)
                
                # 每 60 秒回報一次
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error("回報指標時發生錯誤", error=str(e))
                await asyncio.sleep(60)
    
    async def process_manual_alert(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """處理手動提交的警報。"""
        try:
            # 建立 SecurityAlert 物件
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
            
            # 透過圖處理
            result = await self.graph.process_alert(alert)
            
            return result
            
        except Exception as e:
            logger.error("處理手動警報失敗", error=str(e), exc_info=True)
            raise