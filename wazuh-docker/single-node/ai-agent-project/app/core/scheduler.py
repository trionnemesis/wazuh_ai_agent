"""
排程器模組
負責定期執行威脅情報收集任務
"""

import asyncio
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from typing import Optional

from .config import SCHEDULER_INTERVAL_SECONDS, SCHEDULER_MISFIRE_GRACE_TIME

logger = logging.getLogger(__name__)

# 全域排程器實例
scheduler: Optional[AsyncIOScheduler] = None

def get_scheduler() -> AsyncIOScheduler:
    """獲取排程器實例"""
    global scheduler
    if scheduler is None:
        # 使用當前的事件循環
        try:
            loop = asyncio.get_running_loop()
            scheduler = AsyncIOScheduler(event_loop=loop)
        except RuntimeError:
            # 如果沒有運行中的事件循環，創建一個新的
            scheduler = AsyncIOScheduler()
    return scheduler

async def async_job_wrapper():
    """異步任務包裝器"""
    from services.alert_service import triage_new_alerts
    
    try:
        await triage_new_alerts()
    except Exception as e:
        logger.error(f"執行 triage_new_alerts 時發生錯誤: {str(e)}", exc_info=True)

def start_scheduler():
    """啟動排程器"""
    sched = get_scheduler()
    
    # 添加定時任務 - 直接使用異步函數
    sched.add_job(
        async_job_wrapper,  # 使用異步包裝器
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