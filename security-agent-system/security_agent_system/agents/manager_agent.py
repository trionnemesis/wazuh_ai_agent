"""Manager Agent: Control center for alert triage and task distribution."""
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import json
import hashlib
import structlog
import difflib
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
    Manager Agent - The Control Center
    
    Responsibilities:
    1. Receive and triage incoming alerts
    2. Deduplicate alerts
    3. Create and dispatch tasks
    4. Monitor task lifecycle
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
        
        # Task tracking
        self.active_tasks: Dict[str, Task] = {}
        self.task_history: List[Task] = []
        
        # Deduplication cache
        self.alert_cache: Dict[str, str] = {}  # hash -> task_id
        self.cache_ttl = timedelta(hours=24)
        
        # Performance metrics
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
        """Initialize the Manager Agent."""
        await self.broker.connect()
        logger.info("Manager Agent initialized", agent_id=self.agent_id)
        
    async def start(self) -> None:
        """Start the Manager Agent's main loop."""
        logger.info("Manager Agent starting", agent_id=self.agent_id)
        
        # Start background tasks
        tasks = [
            asyncio.create_task(self._cleanup_cache_loop()),
            asyncio.create_task(self._monitor_tasks_loop()),
            asyncio.create_task(self._metrics_reporting_loop())
        ]
        
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Manager Agent stopping")
            for task in tasks:
                task.cancel()
                
    async def stop(self) -> None:
        """Stop the Manager Agent."""
        await self.broker.disconnect()
        logger.info("Manager Agent stopped", agent_id=self.agent_id)
        
    async def health_check(self) -> Dict[str, Any]:
        """Return agent health status."""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "status": "healthy",
            "active_tasks": len(self.active_tasks),
            "metrics": dict(self.metrics),
            "uptime_seconds": (datetime.utcnow() - datetime.utcnow()).total_seconds()
        }
        
    async def process_alert(self, alert: AlertMessage) -> Task:
        """Process incoming alert and create task."""
        logger.info("Processing alert",
                   alert_id=alert.alert_id,
                   severity=alert.severity,
                   source=alert.source)
                   
        self.metrics["alerts_received"] += 1
        self.metrics["alerts_by_severity"][alert.severity] += 1
        
        # Check for duplicates
        existing_task_id = await self.deduplicate_alert(alert)
        if existing_task_id:
            logger.info("Duplicate alert detected",
                       alert_id=alert.alert_id,
                       existing_task=existing_task_id)
            self.metrics["duplicates_found"] += 1
            return self.active_tasks[existing_task_id]
            
        # Classify alert
        classification = await self.classify_alert(alert)
        
        # Create task
        task = Task(
            alert_id=alert.alert_id,
            alert_source=alert.source,
            alert_timestamp=alert.timestamp,
            severity=alert.severity,
            status=TaskStatus.PENDING,
            title=alert.title,
            affected_assets=alert.affected_assets,
            source_ips=alert.source_ips
        )
        
        # Store task
        self.active_tasks[task.task_id] = task
        self.metrics["tasks_created"] += 1
        self.metrics["alerts_by_category"][classification["category"]] += 1
        
        # Cache alert hash
        alert_hash = self._compute_alert_hash(alert)
        self.alert_cache[alert_hash] = task.task_id
        
        # Dispatch to Hunter Agent if needed
        if classification["requires_hunting"]:
            await self._dispatch_to_hunter(task, alert, classification)
        else:
            # Low priority or false positive
            task.status = TaskStatus.COMPLETED
            logger.info("Alert classified as low priority",
                       alert_id=alert.alert_id,
                       category=classification["category"])
                       
        return task
        
    async def classify_alert(self, alert: AlertMessage) -> Dict[str, Any]:
        """Classify alert using lightweight LLM for routing decisions."""
        prompt = f"""
        Analyze this security alert and provide classification:
        
        Alert: {alert.title}
        Description: {alert.description}
        Severity: {alert.severity}
        Affected Assets: {', '.join(alert.affected_assets)}
        Source IPs: {', '.join(alert.source_ips)}
        
        Classify as:
        1. Threat Category (MALWARE/INTRUSION/DATA_EXFILTRATION/PRIVILEGE_ESCALATION/LATERAL_MOVEMENT/C2/UNKNOWN)
        2. Requires Hunting (true/false)
        3. Priority (low/medium/high/critical)
        4. Confidence (0-100)
        
        Return JSON only.
        """
        
        try:
            response = await self.llm.generate(
                prompt=prompt,
                temperature=0.0,
                max_tokens=200
            )
            
            classification = json.loads(response)
            
            # Validate and set defaults
            classification.setdefault("category", ThreatCategory.UNKNOWN)
            classification.setdefault("requires_hunting", True)
            classification.setdefault("priority", "medium")
            classification.setdefault("confidence", 50)
            
            logger.debug("Alert classified",
                        alert_id=alert.alert_id,
                        classification=classification)
                        
            return classification
            
        except Exception as e:
            logger.error("Failed to classify alert",
                        alert_id=alert.alert_id,
                        error=str(e))
            # Default classification
            return {
                "category": ThreatCategory.UNKNOWN,
                "requires_hunting": True,
                "priority": "high",
                "confidence": 0
            }
            
    async def deduplicate_alert(self, alert: AlertMessage) -> Optional[str]:
        """Check if alert is duplicate, return existing task_id if found."""
        alert_hash = self._compute_alert_hash(alert)
        
        # Check cache
        if alert_hash in self.alert_cache:
            task_id = self.alert_cache[alert_hash]
            if task_id in self.active_tasks:
                return task_id
                
        # Check for similar alerts in active tasks
        for task_id, task in self.active_tasks.items():
            if self._is_similar_alert(alert, task):
                # Update cache
                self.alert_cache[alert_hash] = task_id
                return task_id
                
        return None
        
    async def track_task_status(self, task_id: str, status: TaskStatus) -> None:
        """Update task status in tracking system."""
        if task_id not in self.active_tasks:
            logger.warning("Unknown task ID", task_id=task_id)
            return
            
        task = self.active_tasks[task_id]
        task.status = status
        task.updated_at = datetime.utcnow()
        
        logger.info("Task status updated",
                   task_id=task_id,
                   status=status)
                   
        # Move completed tasks to history
        if status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            self.task_history.append(task)
            del self.active_tasks[task_id]
            
    def _compute_alert_hash(self, alert: AlertMessage) -> str:
        """Compute hash for alert deduplication."""
        # Create hash based on key alert attributes
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
        """Check if alerts are similar enough to be considered duplicates."""
        # Time window check (within 1 hour)
        time_diff = abs((alert.timestamp - task.alert_timestamp).total_seconds())
        if time_diff > 3600:
            return False
            
        # Severity check
        if alert.severity != task.severity:
            return False
            
        # Fuzzy matching on titles
        if task.title:
            similarity = difflib.SequenceMatcher(None, alert.title, task.title).ratio()
            if similarity > 0.8:
                return True

        # IP/Asset overlap
        if task.affected_assets:
            # Check if any asset overlaps
            if any(asset in task.affected_assets for asset in alert.affected_assets):
                return True

        if task.source_ips:
            # Check if any source IP overlaps
            if any(ip in task.source_ips for ip in alert.source_ips):
                return True
        
        return False
        
    async def _dispatch_to_hunter(
        self,
        task: Task,
        alert: AlertMessage,
        classification: Dict[str, Any]
    ) -> None:
        """Dispatch task to Hunter Agent."""
        task.status = TaskStatus.HUNTING
        task.processing_start = datetime.utcnow()
        
        # Create hunting message
        hunting_message = HuntingMessage(
            task=task,
            alert=alert,
            max_depth=3 if classification["priority"] == "critical" else 2,
            time_window_hours=48 if classification["priority"] == "critical" else 24,
            include_threat_intel=True,
            priority=classification["priority"]
        )
        
        # Publish to hunting queue
        await self.broker.publish(
            settings.hunting_queue,
            hunting_message.dict()
        )
        
        logger.info("Task dispatched to Hunter",
                   task_id=task.task_id,
                   priority=classification["priority"])
                   
    async def _cleanup_cache_loop(self) -> None:
        """Periodically clean up old entries from deduplication cache."""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                
                current_time = datetime.utcnow()
                expired_hashes = []
                
                for alert_hash, task_id in self.alert_cache.items():
                    if task_id not in self.active_tasks:
                        # Check task history
                        task = next((t for t in self.task_history if t.task_id == task_id), None)
                        if task and (current_time - task.created_at) > self.cache_ttl:
                            expired_hashes.append(alert_hash)
                            
                # Remove expired entries
                for alert_hash in expired_hashes:
                    del self.alert_cache[alert_hash]
                    
                logger.debug("Cache cleanup completed",
                           removed_entries=len(expired_hashes))
                           
            except Exception as e:
                logger.error("Cache cleanup failed", error=str(e))
                
    async def _monitor_tasks_loop(self) -> None:
        """Monitor task timeouts and stuck tasks."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                current_time = datetime.utcnow()
                
                for task_id, task in list(self.active_tasks.items()):
                    # Check for timeouts
                    if task.processing_start:
                        processing_time = (current_time - task.processing_start).total_seconds()
                        
                        if processing_time > settings.manager_config["task_timeout_seconds"]:
                            logger.warning("Task timeout detected",
                                         task_id=task_id,
                                         processing_seconds=processing_time)
                                         
                            # Handle timeout
                            task.status = TaskStatus.FAILED
                            task.error_message = "Task timeout"
                            
                            # Move to DLQ or retry
                            if task.retry_count < settings.manager_config.get("retry_attempts", 3):
                                task.retry_count += 1
                                await self._dispatch_to_hunter(
                                    task,
                                    AlertMessage(**task.dict()),  # Reconstruct alert
                                    {"priority": "high", "category": "UNKNOWN"}
                                )
                            else:
                                await self.track_task_status(task_id, TaskStatus.FAILED)
                                
            except Exception as e:
                logger.error("Task monitoring failed", error=str(e))
                
    async def _metrics_reporting_loop(self) -> None:
        """Report metrics periodically."""
        while True:
            try:
                await asyncio.sleep(300)  # Report every 5 minutes
                
                logger.info("Manager Agent metrics",
                          metrics=dict(self.metrics),
                          active_tasks=len(self.active_tasks),
                          cache_size=len(self.alert_cache))
                          
            except Exception as e:
                logger.error("Metrics reporting failed", error=str(e))
