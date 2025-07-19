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