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
from ..services.cache_service import cache_service


router = APIRouter()

# 包含子路由器
router.include_router(cache_router)

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
            "Attack path discovery",
            "Intelligent caching for embeddings"
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
    快取統計端點 - 返回快取使用情況和效能指標
    
    Returns:
        Dict: 快取統計資訊，包括命中率、大小等
    """
    stats = cache_service.get_stats()
    return {
        "timestamp": datetime.now().isoformat(),
        "cache_stats": stats,
        "cache_config": {
            "query_cache_ttl": "5 minutes",
            "vector_cache_type": "LRU",
            "graph_cache_ttl": "10 minutes"
        }
    }

@router.post("/cache/invalidate/{cache_type}")
async def invalidate_cache(cache_type: str, key: str = None):
    """
    使快取無效端點 - 清除指定類型的快取
    
    Args:
        cache_type: 快取類型 (query, vector, graph)
        key: 可選，特定的快取鍵
        
    Returns:
        Dict: 操作結果
    """
    try:
        cache_service.invalidate(cache_type, key)
        return {
            "status": "success",
            "message": f"Cache '{cache_type}' invalidated" + (f" for key '{key}'" if key else ""),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }