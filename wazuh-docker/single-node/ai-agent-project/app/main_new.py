"""
Wazuh GraphRAG AI Agent
主程式進入點 - 精簡化的模組化架構
"""

import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager

from core.config import (
    APP_TITLE, APP_VERSION, validate_config,
    CACHE_ENABLED, CACHE_LRU_MAXSIZE, CACHE_TTL_MAXSIZE, CACHE_TTL_SECONDS
)
from core.scheduler import start_scheduler, shutdown_scheduler
from api.endpoints import router as api_router
from services.opensearch_service import close_opensearch_client
from services.neo4j_service import close_neo4j_driver
from utils.cache_manager import initialize_cache_service

# 配置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用程式生命週期管理"""
    # 啟動時
    logger.info(f"🚀 {APP_TITLE} v{APP_VERSION} starting up...")
    
    # 驗證配置
    validate_config()
    
    # 初始化快取服務
    cache_service = initialize_cache_service(
        lru_maxsize=CACHE_LRU_MAXSIZE,
        ttl_maxsize=CACHE_TTL_MAXSIZE,
        ttl_seconds=CACHE_TTL_SECONDS,
        enable_cache=CACHE_ENABLED
    )
    if cache_service:
        logger.info("✅ 智能快取服務已啟動")
    
    # 啟動排程器
    start_scheduler()
    
    yield
    
    # 關閉時
    logger.info("🛑 Shutting down...")
    
    # 關閉排程器
    shutdown_scheduler()
    
    # 關閉資料庫連接
    await close_opensearch_client()
    await close_neo4j_driver()
    
    logger.info("👋 Shutdown complete")

# 創建 FastAPI 應用
app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    lifespan=lifespan
)

# 註冊路由
app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)