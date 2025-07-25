"""
健康檢查模組
專門處理系統健康檢查邏輯
"""

import logging
from datetime import datetime
from typing import Dict, Any

from core.config import APP_VERSION, APP_STAGE


from services.opensearch_service import get_opensearch_client
from services.neo4j_service import get_neo4j_driver
from embedding_service import GeminiEmbeddingService
from utils.cache_manager import get_cache_service


logger = logging.getLogger(__name__)


async def perform_health_check() -> Dict[str, Any]:
    """
    執行詳細的健康檢查
    
    Returns:
        Dict: 包含各個組件健康狀態的詳細報告
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": APP_VERSION,
        "stage": APP_STAGE,
        "components": {}
    }

    # 檢查 OpenSearch
    health_status["components"]["opensearch"] = await check_opensearch_health()

    # 檢查 Neo4j
    health_status["components"]["neo4j"] = await check_neo4j_health()

    # 檢查嵌入服務
    health_status["components"]["embedding_service"] = (
        await check_embedding_service_health()
    )

    # 檢查快取服務
    health_status["components"]["cache_service"] = await check_cache_health()

    # 判斷整體健康狀態
    if any(
        comp["status"] != "healthy"
        for comp in health_status["components"].values()
    ):
        health_status["status"] = "degraded"

    return health_status


async def check_opensearch_health() -> Dict[str, Any]:
    """檢查 OpenSearch 連線狀態"""
    try:
        client = get_opensearch_client()
        info = await client.info()

        # 檢查向量索引
        index_exists = await client.indices.exists(
            index="wazuh-alerts-vectors"
        )

        return {
            "status": "healthy",
            "cluster_name": info.get("cluster_name", "unknown"),
            "version": info.get("version", {}).get("number", "unknown"),
            "vector_index_exists": index_exists
        }
    except Exception as e:
        logger.error(f"OpenSearch 健康檢查失敗: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


async def check_neo4j_health() -> Dict[str, Any]:
    """檢查 Neo4j 連線狀態"""
    try:
        driver = get_neo4j_driver()
        if not driver:
            return {
                "status": "unavailable",
                "message": "Neo4j driver not initialized"
            }

        async with driver.session() as session:
            result = await session.run("RETURN 1 as test")
            await result.single()

        return {
            "status": "healthy",
            "message": "Neo4j connection successful"
        }
    except Exception as e:
        logger.error(f"Neo4j 健康檢查失敗: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


async def check_embedding_service_health() -> Dict[str, Any]:
    """檢查嵌入服務狀態"""
    try:
        embedding_service = GeminiEmbeddingService()

        # 測試向量化功能
        test_text = "Health check test"
        vector = await embedding_service.embed_documents([test_text])

        return {
            "status": "healthy",
            "embedding_dimension": (
                len(vector[0]) if vector and len(vector) > 0 else 0
            ),
            "service_type": "Gemini"
        }
    except Exception as e:
        logger.error(f"嵌入服務健康檢查失敗: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


async def check_cache_health() -> Dict[str, Any]:
    """檢查快取服務狀態"""
    try:
        cache_service = get_cache_service()
        if cache_service is None:
            raise ValueError("Cache service 未初始化")
        stats = cache_service.get_stats()
        return {
            "status": "healthy",
            "hit_rate": stats['hit_rate'],
            "total_requests": stats['total_requests'],
            "hits": stats['hits'],
            "misses": stats['misses'],
            "cache_sizes": {
                "query_cache": (
                    f"{stats['query_cache_size']}/"
                    f"{stats['query_cache_maxsize']}"
                ),
                "vector_cache": (
                    f"{stats['vector_cache_size']}/"
                    f"{stats['vector_cache_maxsize']}"
                ),
                "graph_cache": (
                    f"{stats['graph_cache_size']}/"
                    f"{stats['graph_cache_maxsize']}"
                )
            }
        }
    except Exception as e:
        logger.error(f"快取服務健康檢查失敗: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }