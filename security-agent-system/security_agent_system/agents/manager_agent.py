"""管理代理：警報分類與任務分發的控制中心。"""
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import json
import hashlib
import structlog
from collections import defaultdict

from ..core.interfaces import IManagerAgent, IMessageBroker, ILLMProvider
from ..core.models import (
    Task, TaskStatus, AlertMessage, HuntingMessage,
    AlertSeverity, ThreatCategory
)
from ..core.config import settings

logger = structlog.get_logger()


class ManagerAgent(IManagerAgent):
    """
    管理代理 - 控制中心
    
    職責：
    1. 接收並分類傳入的警報
    2. 警報去重
    3. 建立並分發任務
    4. 監控任務生命週期
    """
    
    def __init__(
        self,
        message_broker: IMessageBroker,
        llm_provider: ILLMProvider
    ):
        self._agent_id = f"manager-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        self._agent_type = "manager"
        self.broker = message_broker
        self.llm = llm_provider
        
        # 任務追蹤
        self.active_tasks: Dict[str, Task] = {}
        self.task_history: List[Task] = []
        
        # 去重快取
        self.alert_cache: Dict[str, str] = {}  # 雜湊值 -> 任務ID
        self.cache_ttl = timedelta(hours=24)
        
        # 效能指標
        self.metrics = {
            "alerts_received": 0,
            "tasks_created": 0,
            "duplicates_found": 0,
            "alerts_by_severity": defaultdict(int),
            "alerts_by_category": defaultdict(int)
        }
        
    @property
    def agent_id(self) -> str:
        return self._agent_id
        
    @property
    def agent_type(self) -> str:
        return self._agent_type
        
    async def initialize(self) -> None:
        """初始化管理代理。"""
        await self.broker.connect()
        logger.info("管理代理已初始化", agent_id=self.agent_id)
        
    async def start(self) -> None:
        """啟動管理代理的主迴圈。"""
        logger.info("管理代理啟動中", agent_id=self.agent_id)
        
        # 啟動背景任務
        tasks = [
            asyncio.create_task(self._cleanup_cache_loop()),
            asyncio.create_task(self._monitor_tasks_loop()),
            asyncio.create_task(self._metrics_reporting_loop())
        ]
        
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("管理代理停止中")
            for task in tasks:
                task.cancel()
                
    async def stop(self) -> None:
        """停止管理代理。"""
        await self.broker.disconnect()
        logger.info("管理代理已停止", agent_id=self.agent_id)
        
    async def health_check(self) -> Dict[str, Any]:
        """返回代理健康狀態。"""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "status": "healthy",
            "active_tasks": len(self.active_tasks),
            "metrics": dict(self.metrics),
            "uptime_seconds": (datetime.utcnow() - datetime.utcnow()).total_seconds()
        }
        
    async def process_alert(self, alert: AlertMessage) -> Task:
        """處理傳入的警報並建立任務。"""
        logger.info("正在處理警報",
                   alert_id=alert.alert_id,
                   severity=alert.severity,
                   source=alert.source)
                   
        self.metrics["alerts_received"] += 1
        self.metrics["alerts_by_severity"][alert.severity] += 1
        
        # 檢查重複項
        existing_task_id = await self.deduplicate_alert(alert)
        if existing_task_id:
            logger.info("偵測到重複警報",
                       alert_id=alert.alert_id,
                       existing_task=existing_task_id)
            self.metrics["duplicates_found"] += 1
            return self.active_tasks[existing_task_id]
            
        # 分類警報
        classification = await self.classify_alert(alert)
        
        # 建立任務
        task = Task(
            alert_id=alert.alert_id,
            alert_source=alert.source,
            alert_timestamp=alert.timestamp,
            severity=alert.severity,
            status=TaskStatus.PENDING
        )
        
        # 儲存任務
        self.active_tasks[task.task_id] = task
        self.metrics["tasks_created"] += 1
        self.metrics["alerts_by_category"][classification["category"]] += 1
        
        # 快取警報雜湊值
        alert_hash = self._compute_alert_hash(alert)
        self.alert_cache[alert_hash] = task.task_id
        
        # 如果需要，分派給獵人代理
        if classification["requires_hunting"]:
            await self._dispatch_to_hunter(task, alert, classification)
        else:
            # 低優先級或誤報
            task.status = TaskStatus.COMPLETED
            logger.info("警報被分類為低優先級",
                       alert_id=alert.alert_id,
                       category=classification["category"])
                       
        return task
        
    async def classify_alert(self, alert: AlertMessage) -> Dict[str, Any]:
        """使用輕量級 LLM 對警報進行分類以做出路由決策。"""
        prompt = f"""
        分析此安全警報並提供分類：
        
        警報：{alert.title}
        描述：{alert.description}
        嚴重性：{alert.severity}
        受影響資產：{', '.join(alert.affected_assets)}
        來源 IP：{', '.join(alert.source_ips)}
        
        分類為：
        1. 威脅類別 (MALWARE/INTRUSION/DATA_EXFILTRATION/PRIVILEGE_ESCALATION/LATERAL_MOVEMENT/C2/UNKNOWN)
        2. 需要狩獵 (true/false)
        3. 優先級 (low/medium/high/critical)
        4. 信賴度 (0-100)
        
        僅返回 JSON。
        """
        
        try:
            response = await self.llm.generate(
                prompt=prompt,
                temperature=0.0,
                max_tokens=200
            )
            
            classification = json.loads(response)
            
            # 驗證並設定預設值
            classification.setdefault("category", ThreatCategory.UNKNOWN)
            classification.setdefault("requires_hunting", True)
            classification.setdefault("priority", "medium")
            classification.setdefault("confidence", 50)
            
            logger.debug("警報已分類",
                        alert_id=alert.alert_id,
                        classification=classification)
                        
            return classification
            
        except Exception as e:
            logger.error("分類警報失敗",
                        alert_id=alert.alert_id,
                        error=str(e))
            # 預設分類
            return {
                "category": ThreatCategory.UNKNOWN,
                "requires_hunting": True,
                "priority": "high",
                "confidence": 0
            }
            
    async def deduplicate_alert(self, alert: AlertMessage) -> Optional[str]:
        """檢查警報是否重複，如果找到則返回現有 task_id。"""
        alert_hash = self._compute_alert_hash(alert)
        
        # 檢查快取
        if alert_hash in self.alert_cache:
            task_id = self.alert_cache[alert_hash]
            if task_id in self.active_tasks:
                return task_id
                
        # 檢查活動任務中是否有相似警報
        for task_id, task in self.active_tasks.items():
            if self._is_similar_alert(alert, task):
                # 更新快取
                self.alert_cache[alert_hash] = task_id
                return task_id
                
        return None
        
    async def track_task_status(self, task_id: str, status: TaskStatus) -> None:
        """在追蹤系統中更新任務狀態。"""
        if task_id not in self.active_tasks:
            logger.warning("未知的任務 ID", task_id=task_id)
            return
            
        task = self.active_tasks[task_id]
        task.status = status
        task.updated_at = datetime.utcnow()
        
        logger.info("任務狀態已更新",
                   task_id=task_id,
                   status=status)
                   
        # 將已完成的任務移至歷史記錄
        if status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            self.task_history.append(task)
            del self.active_tasks[task_id]
            
    def _compute_alert_hash(self, alert: AlertMessage) -> str:
        """計算警報雜湊值以進行去重。"""
        # 根據關鍵警報屬性建立雜湊值
        hash_data = {
            "source": alert.source,
            "title": alert.title,
            "affected_assets": sorted(alert.affected_assets),
            "source_ips": sorted(alert.source_ips),
            "file_hashes": sorted(alert.file_hashes)
        }
        
        hash_string = json.dumps(hash_data, sort_keys=True)
        return hashlib.sha256(hash_string.encode()).hexdigest()
        
    def _is_similar_alert(self, alert: AlertMessage, task: Task) -> bool:
        """檢查警報是否足夠相似以被視為重複。"""
        # 時間窗口檢查（1小時內）
        time_diff = abs((alert.timestamp - task.alert_timestamp).total_seconds())
        if time_diff > 3600:
            return False
            
        # 嚴重性檢查
        if alert.severity != task.severity:
            return False
            
        # 待辦事項：實現更複雜的相似性檢查
        # - 標題的模糊匹配
        # - IP/資產重疊
        # - 模式匹配
        
        return False
        
    async def _dispatch_to_hunter(
        self,
        task: Task,
        alert: AlertMessage,
        classification: Dict[str, Any]
    ) -> None:
        """將任務分派給獵人代理。"""
        task.status = TaskStatus.HUNTING
        task.processing_start = datetime.utcnow()
        
        # 建立狩獵訊息
        hunting_message = HuntingMessage(
            task=task,
            alert=alert,
            max_depth=3 if classification["priority"] == "critical" else 2,
            time_window_hours=48 if classification["priority"] == "critical" else 24,
            include_threat_intel=True,
            priority=classification["priority"]
        )
        
        # 發布到狩獵佇列
        await self.broker.publish(
            settings.hunting_queue,
            hunting_message.dict()
        )
        
        logger.info("任務已分派給獵人",
                   task_id=task.task_id,
                   priority=classification["priority"])
                   
    async def _cleanup_cache_loop(self) -> None:
        """定期清理去重快取中的舊條目。"""
        while True:
            try:
                await asyncio.sleep(3600)  # 每小時執行一次
                
                current_time = datetime.utcnow()
                expired_hashes = []
                
                for alert_hash, task_id in self.alert_cache.items():
                    if task_id not in self.active_tasks:
                        # 檢查任務歷史記錄
                        task = next((t for t in self.task_history if t.task_id == task_id), None)
                        if task and (current_time - task.created_at) > self.cache_ttl:
                            expired_hashes.append(alert_hash)
                            
                # 移除過期條目
                for alert_hash in expired_hashes:
                    del self.alert_cache[alert_hash]
                    
                logger.debug("快取清理完成",
                           removed_entries=len(expired_hashes))
                           
            except Exception as e:
                logger.error("快取清理失敗", error=str(e))
                
    async def _monitor_tasks_loop(self) -> None:
        """監控任務逾時和卡住的任務。"""
        while True:
            try:
                await asyncio.sleep(60)  # 每分鐘檢查一次
                
                current_time = datetime.utcnow()
                
                for task_id, task in list(self.active_tasks.items()):
                    # 檢查逾時
                    if task.processing_start:
                        processing_time = (current_time - task.processing_start).total_seconds()
                        
                        if processing_time > settings.manager_config["task_timeout_seconds"]:
                            logger.warning("偵測到任務逾時",
                                         task_id=task_id,
                                         processing_seconds=processing_time)
                                         
                            # 處理逾時
                            task.status = TaskStatus.FAILED
                            task.error_message = "任務逾時"
                            
                            # 移至死信佇列或重試
                            if task.retry_count < settings.manager_config.get("retry_attempts", 3):
                                task.retry_count += 1
                                await self._dispatch_to_hunter(
                                    task,
                                    AlertMessage(**task.dict()),  # 重建警報
                                    {"priority": "high", "category": "UNKNOWN"}
                                )
                            else:
                                await self.track_task_status(task_id, TaskStatus.FAILED)
                                
            except Exception as e:
                logger.error("任務監控失敗", error=str(e))
                
    async def _metrics_reporting_loop(self) -> None:
        """定期回報指標。"""
        while True:
            try:
                await asyncio.sleep(300)  # 每 5 分鐘回報一次
                
                logger.info("管理代理指標",
                          metrics=dict(self.metrics),
                          active_tasks=len(self.active_tasks),
                          cache_size=len(self.alert_cache))
                          
            except Exception as e:
                logger.error("指標回報失敗", error=str(e))