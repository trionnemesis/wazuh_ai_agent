"""
API 端點模組
包含所有 FastAPI 路由定義
"""

from datetime import datetime
from fastapi import APIRouter, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from ..core.config import get_config_summary, APP_STAGE
from ..core.scheduler import get_scheduler_status
from ..api.health_check import perform_health_check
from ..services.metrics import REGISTRY
from ..utils.cache_manager import get_cache_service

router = APIRouter()

@router.get("/")
async def read_root():
    """根端點 - 返回服務狀態資訊"""
    return {
        "status": "AI Triage Agent with GraphRAG is running", 
        "scheduler_status": get_scheduler_status(),
        "stage": APP_STAGE,
        "features": [
            "Dynamic contextual query generation",
            "Multi-source data retrieval",
            "Cross-referential analysis",
            "Enhanced decision engine",
            "Prometheus monitoring integration",
            "Graph-based threat analysis",
            "Attack path discovery"
        ],
        "config": get_config_summary()
    }

@router.get("/health")
async def health_check():
    """
    詳細健康檢查端點
    
    提供完整的系統狀態資訊，包括：
    - OpenSearch 連線狀態
    - Neo4j 連線狀態
    - 嵌入服務可用性
    - 向量化統計資料
    - 系統配置資訊
    
    Returns:
        Dict: 詳細的健康檢查報告
    """
    return await perform_health_check()

@router.get("/metrics")
async def get_metrics():
    """Prometheus 指標端點 - 暴露應用程式效能指標"""
    return Response(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST
    )

@router.get("/cache/stats")
async def get_cache_stats():
    """
    快取統計資訊端點
    
    返回智能快取服務的統計資料，包括：
    - 快取命中率
    - 總請求數
    - 快取大小
    - 節省的時間
    
    Returns:
        Dict: 快取統計資訊
    """
    cache_service = get_cache_service()
    if not cache_service:
        return {
            "status": "disabled",
            "message": "快取服務未啟用"
        }
    
    stats = cache_service.get_stats()
    info = cache_service.get_cache_info()
    
    return {
        "status": "enabled",
        "statistics": stats,
        "cache_info": info,
        "timestamp": datetime.utcnow().isoformat()
    }

@router.post("/cache/clear")
async def clear_cache(cache_type: str = None):
    """
    清除快取端點
    
    Args:
        cache_type: 要清除的快取類型 ('lru', 'ttl', 或 None 表示全部)
    
    Returns:
        Dict: 清除結果
    """
    cache_service = get_cache_service()
    if not cache_service:
        return {
            "status": "error",
            "message": "快取服務未啟用"
        }
    
    cache_service.clear_cache(cache_type)
    
    return {
        "status": "success",
        "message": f"快取已清除: {cache_type or 'all'}",
        "timestamp": datetime.utcnow().isoformat()
    }