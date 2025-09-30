"""用於管理三代理系統的代理協調器。"""
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
    """協調三代理安全系統。"""
    
    def __init__(self):
        self.agents: Dict[str, Any] = {}
        self.infrastructure: Dict[str, Any] = {}
        self.is_running = False
        
    async def initialize(self) -> None:
        """初始化所有系統組件。"""
        logger.info("正在初始化安全代理系統")
        
        # 初始化基礎設施
        await self._initialize_infrastructure()
        
        # 初始化代理
        await self._initialize_agents()
        
        logger.info("系統初始化完成")
        
    async def _initialize_infrastructure(self) -> None:
        """初始化基礎設施組件。"""
        # 訊息代理
        if settings.broker_type == MessageBrokerType.RABBITMQ:
            self.infrastructure["broker"] = RabbitMQBroker()
        else:
            self.infrastructure["broker"] = KafkaBroker()
            
        # 圖形資料庫
        self.infrastructure["graph_db"] = Neo4jDatabase()
        
        # 向量資料庫
        self.infrastructure["vector_db"] = ChromaDatabase()
        
        # LLM 供應商
        self.infrastructure["llm_providers"] = {
            LLMProvider.OPENAI: OpenAIProvider(),
            LLMProvider.ANTHROPIC: AnthropicProvider(),
            LLMProvider.GOOGLE: GoogleProvider()
        }
        
        # 通知服務
        self.infrastructure["notifier"] = SlackNotificationService()
        
        # 行動執行器
        self.infrastructure["action_executor"] = ActionExecutorService()
        
        logger.info("基礎設施組件已建立")
        
    async def _initialize_agents(self) -> None:
        """初始化三個代理。"""
        # 管理代理
        manager_llm = self.infrastructure["llm_providers"][
            LLMProvider[settings.manager_config["llm_provider"]]
        ]
        
        self.agents["manager"] = ManagerAgent(
            message_broker=self.infrastructure["broker"],
            llm_provider=manager_llm
        )
        
        # 獵人代理
        hunter_llm = self.infrastructure["llm_providers"][
            LLMProvider[settings.hunter_config["llm_provider"]]
        ]
        
        self.agents["hunter"] = HunterAgent(
            message_broker=self.infrastructure["broker"],
            graph_db=self.infrastructure["graph_db"],
            vector_db=self.infrastructure["vector_db"],
            llm_provider=hunter_llm
        )
        
        # 執行者代理
        executor_llm = self.infrastructure["llm_providers"][
            LLMProvider[settings.executor_config["llm_provider"]]
        ]
        
        self.agents["executor"] = ExecutorAgent(
            message_broker=self.infrastructure["broker"],
            llm_provider=executor_llm,
            notification_service=self.infrastructure["notifier"],
            action_executor=self.infrastructure["action_executor"]
        )
        
        # 初始化所有代理
        await asyncio.gather(
            self.agents["manager"].initialize(),
            self.agents["hunter"].initialize(),
            self.agents["executor"].initialize()
        )
        
        logger.info("所有代理已初始化")
        
    async def start(self) -> None:
        """啟動代理系統。"""
        if self.is_running:
            logger.warning("系統已在執行中")
            return
            
        logger.info("正在啟動安全代理系統")
        self.is_running = True
        
        # 啟動所有代理
        agent_tasks = [
            asyncio.create_task(self.agents["manager"].start()),
            asyncio.create_task(self.agents["hunter"].start()),
            asyncio.create_task(self.agents["executor"].start())
        ]
        
        # 啟動監控
        monitor_task = asyncio.create_task(self._monitor_system())
        
        # 啟動 API 伺服器
        api_task = asyncio.create_task(self._start_api_server())
        
        try:
            # 執行直到被取消
            await asyncio.gather(
                *agent_tasks,
                monitor_task,
                api_task
            )
        except asyncio.CancelledError:
            logger.info("請求系統關閉")
        finally:
            self.is_running = False
            
    async def stop(self) -> None:
        """優雅地停止代理系統。"""
        logger.info("正在停止安全代理系統")
        
        # 停止所有代理
        await asyncio.gather(
            self.agents["manager"].stop(),
            self.agents["hunter"].stop(),
            self.agents["executor"].stop()
        )
        
        # 斷開基礎設施連線
        if "broker" in self.infrastructure:
            await self.infrastructure["broker"].disconnect()
        if "graph_db" in self.infrastructure:
            await self.infrastructure["graph_db"].disconnect()
        if "vector_db" in self.infrastructure:
            await self.infrastructure["vector_db"].disconnect()
            
        self.is_running = False
        logger.info("系統已停止")
        
    async def process_alert(self, alert_data: Dict[str, Any]) -> str:
        """處理新的安全警報。"""
        try:
            # 建立警報訊息
            alert = AlertMessage(**alert_data)
            
            # 傳送給管理代理
            task = await self.agents["manager"].process_alert(alert)
            
            logger.info("警報已處理",
                       task_id=task.task_id,
                       alert_id=alert.alert_id)
                       
            return task.task_id
            
        except Exception as e:
            logger.error("處理警報失敗", error=str(e))
            raise
            
    async def get_system_status(self) -> Dict[str, Any]:
        """獲取目前系統狀態。"""
        status = {
            "is_running": self.is_running,
            "timestamp": datetime.utcnow().isoformat(),
            "agents": {},
            "infrastructure": {}
        }
        
        # 獲取代理健康狀態
        for name, agent in self.agents.items():
            try:
                health = await agent.health_check()
                status["agents"][name] = health
            except Exception as e:
                status["agents"][name] = {
                    "status": "error",
                    "error": str(e)
                }
                
        # 檢查基礎設施健康狀態
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
        """監控系統健康與效能。"""
        while self.is_running:
            try:
                await asyncio.sleep(60)  # 每分鐘檢查一次
                
                # 獲取系統狀態
                status = await self.get_system_status()
                
                # 檢查問題
                issues = []
                
                for agent_name, agent_status in status["agents"].items():
                    if agent_status.get("status") != "healthy":
                        issues.append(f"代理 {agent_name} 不健康")
                        
                # 如果發現問題則發出警報
                if issues:
                    logger.warning("偵測到系統健康問題",
                                 issues=issues)
                                 
                    # 傳送通知
                    if self.infrastructure.get("notifier"):
                        await self.infrastructure["notifier"].send_alert(
                            title="系統健康警報",
                            message=f"偵測到問題：{', '.join(issues)}",
                            severity="warning"
                        )
                        
            except Exception as e:
                logger.error("系統監控錯誤", error=str(e))
                
    async def _start_api_server(self) -> None:
        """啟動用於外部互動的 API 伺服器。"""
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import JSONResponse
        import uvicorn
        
        app = FastAPI(title="安全代理系統 API")
        
        @app.get("/health")
        async def health_check():
            """系統健康檢查端點。"""
            return await self.get_system_status()
            
        @app.post("/alerts")
        async def submit_alert(alert_data: Dict[str, Any]):
            """提交新的安全警報。"""
            try:
                task_id = await self.process_alert(alert_data)
                return {"task_id": task_id, "status": "accepted"}
            except Exception as e:
                raise HTTPException(status_code=400, detail=str(e))
                
        @app.get("/tasks/{task_id}")
        async def get_task_status(task_id: str):
            """獲取任務狀態。"""
            # 與管理代理確認
            manager = self.agents.get("manager")
            if not manager:
                raise HTTPException(status_code=503, detail="管理代理不可用")
                
            task = manager.active_tasks.get(task_id) or next(
                (t for t in manager.task_history if t.task_id == task_id), None
            )
            
            if not task:
                raise HTTPException(status_code=404, detail="找不到任務")
                
            return task.dict()
            
        @app.post("/approvals/{request_id}")
        async def handle_approval(request_id: str, approval_data: Dict[str, Any]):
            """處理批准回應。"""
            executor = self.agents.get("executor")
            if not executor:
                raise HTTPException(status_code=503, detail="執行者代理不可用")
                
            await executor.handle_approval_response(
                request_id=request_id,
                approved=approval_data.get("approved", False),
                approver=approval_data.get("approver", "unknown"),
                comments=approval_data.get("comments")
            )
            
            return {"status": "processed"}
            
        @app.get("/metrics")
        async def get_metrics():
            """獲取系統指標。"""
            metrics = {}
            
            for name, agent in self.agents.items():
                metrics[name] = agent.metrics
                
            return metrics
            
        # 執行伺服器
        config = uvicorn.Config(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info"
        )
        server = uvicorn.Server(config)
        
        logger.info("API 伺服器正在 8000 連接埠啟動")
        await server.serve()
        
    async def handle_approval_callback(
        self,
        request_id: str,
        approved: bool,
        approver: str,
        comments: Optional[str] = None
    ) -> None:
        """處理來自外部系統的批准回呼。"""
        executor = self.agents.get("executor")
        if executor:
            await executor.handle_approval_response(
                request_id, approved, approver, comments
            )
        else:
            logger.error("執行者代理不可用，無法處理批准回呼")