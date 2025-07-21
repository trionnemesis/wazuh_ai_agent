# === 快取統計 API 端點 ===
#
# 提供快取狀態監控和管理功能的 RESTful API
#
# 版本: 1.0
# 創建: 2024年12月

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import logging
from ..embedding_service import GeminiEmbeddingService

# 獲取日誌記錄器
logger = logging.getLogger(__name__)

# 創建路由器
router = APIRouter(
    prefix="/api/cache",
    tags=["cache"],
    responses={
        404: {"description": "Not found"},
        500: {"description": "Internal server error"}
    }
)

# 全局服務實例
_embedding_service = None


def get_embedding_service() -> GeminiEmbeddingService:
    """獲取嵌入服務實例"""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = GeminiEmbeddingService()
    return _embedding_service


@router.get("/stats", response_model=Dict[str, Any])
async def get_cache_stats():
    """
    獲取快取統計資訊
    
    返回快取的詳細統計資訊，包括：
    - 啟用狀態
    - 當前大小和最大容量
    - 命中率和使用率
    - 命中/未命中/淘汰次數
    - TTL 設定
    
    Returns:
        Dict[str, Any]: 快取統計資訊
        
    Example Response:
        {
            "enabled": true,
            "size": 150,
            "maxsize": 1000,
            "ttl": 3600,
            "hits": 450,
            "misses": 50,
            "evictions": 10,
            "total_requests": 500,
            "hit_rate": "90.00%",
            "usage_rate": "15.00%",
            "last_reset": "2024-12-01T10:00:00"
        }
    """
    try:
        service = get_embedding_service()
        stats = service.get_cache_stats()
        
        logger.info(f"快取統計查詢成功 - 命中率: {stats['hit_rate']}, 使用率: {stats['usage_rate']}")
        return stats
        
    except Exception as e:
        logger.error(f"獲取快取統計失敗: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear")
async def clear_cache():
    """
    清空快取
    
    清除所有快取的向量嵌入結果。這在以下情況下很有用：
    - 模型參數更新後
    - 記憶體不足時
    - 測試或調試時需要強制重新計算
    
    Returns:
        Dict[str, str]: 操作結果
        
    Example Response:
        {
            "status": "success",
            "message": "Cache cleared successfully"
        }
    """
    try:
        service = get_embedding_service()
        service.clear_cache()
        
        logger.info("快取已成功清空")
        return {
            "status": "success",
            "message": "Cache cleared successfully"
        }
        
    except Exception as e:
        logger.error(f"清空快取失敗: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset-stats")
async def reset_cache_stats():
    """
    重置快取統計
    
    重置所有統計計數器（命中、未命中、淘汰等），但保留快取內容。
    這對於開始新的效能測量週期很有用。
    
    Returns:
        Dict[str, str]: 操作結果
        
    Example Response:
        {
            "status": "success",
            "message": "Cache statistics reset successfully"
        }
    """
    try:
        service = get_embedding_service()
        service.cache_manager.reset_stats()
        
        logger.info("快取統計已重置")
        return {
            "status": "success",
            "message": "Cache statistics reset successfully"
        }
        
    except Exception as e:
        logger.error(f"重置快取統計失敗: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
async def get_cache_config():
    """
    獲取快取配置
    
    返回當前的快取配置參數
    
    Returns:
        Dict[str, Any]: 快取配置資訊
        
    Example Response:
        {
            "enabled": true,
            "maxsize": 1000,
            "ttl": 3600,
            "prefix_query": "query_embed",
            "prefix_document": "doc_embed"
        }
    """
    try:
        service = get_embedding_service()
        cache_manager = service.cache_manager
        
        config = {
            "enabled": cache_manager.enabled,
            "maxsize": cache_manager.maxsize,
            "ttl": cache_manager.ttl,
            "prefix_query": "query_embed",
            "prefix_document": "doc_embed"
        }
        
        return config
        
    except Exception as e:
        logger.error(f"獲取快取配置失敗: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))