"""
排程器模組
負責管理 APScheduler 的設定與任務定義
"""

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from typing import Optional

from ..core.config import SCHEDULER_INTERVAL_SECONDS, SCHEDULER_MISFIRE_GRACE_TIME

logger = logging.getLogger(__name__)

# 全域排程器實例
scheduler: Optional[AsyncIOScheduler] = None

def get_scheduler() -> AsyncIOScheduler:
    """獲取排程器實例"""
    global scheduler
    if scheduler is None:
        scheduler = AsyncIOScheduler()
    return scheduler

def start_scheduler():
    """啟動排程器"""
    from ..services.alert_service import triage_new_alerts  # 避免循環導入
    
    sched = get_scheduler()
    
    # 添加定時任務
    sched.add_job(
        triage_new_alerts, 
        'interval', 
        seconds=SCHEDULER_INTERVAL_SECONDS, 
        id='agentic_triage_job', 
        misfire_grace_time=SCHEDULER_MISFIRE_GRACE_TIME
    )
    
    sched.start()
    logger.info(f"排程器已啟動，每 {SCHEDULER_INTERVAL_SECONDS} 秒執行一次任務")

def shutdown_scheduler():
    """關閉排程器"""
    sched = get_scheduler()
    if sched and sched.running:
        sched.shutdown()
        logger.info("排程器已關閉")

def get_scheduler_status() -> str:
    """獲取排程器狀態"""
    sched = get_scheduler()
    if sched:
        jobs = sched.get_jobs()
        return f"排程器運行中，當前任務數: {len(jobs)}"
    return "排程器未初始化"