"""
Neo4j 適配器模組
統一處理 Neo4j 的可用性檢查和降級策略
"""

import os
import logging
from typing import Optional, Dict, Any, List
from functools import wraps
import asyncio

logger = logging.getLogger(__name__)

# 嘗試導入 Neo4j
try:
    from neo4j import AsyncGraphDatabase, AsyncDriver
    NEO4J_AVAILABLE = True
except ImportError:
    logger.warning("Neo4j 驅動程式不可用。圖形功能將被停用。")
    NEO4J_AVAILABLE = False
    AsyncGraphDatabase = None
    AsyncDriver = None


class Neo4jAdapter:
    """Neo4j 適配器類，提供統一的介面和降級處理"""
    
    def __init__(self):
        self.driver: Optional[AsyncDriver] = None
        self.is_available = NEO4J_AVAILABLE
        self.is_connected = False
        self._connection_error_logged = False
        
        # 從環境變數讀取配置
        self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = os.getenv("NEO4J_USER", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "password")
        self.database = os.getenv("NEO4J_DATABASE", "neo4j")
        
    async def connect(self) -> bool:
        """
        嘗試連接到 Neo4j
        
        Returns:
            bool: 連接是否成功
        """
        if not self.is_available:
            return False
            
        try:
            self.driver = AsyncGraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password)
            )
            # 測試連接
            async with self.driver.session(database=self.database) as session:
                await session.run("RETURN 1")
            
            self.is_connected = True
            logger.info("成功連接到 Neo4j 資料庫")
            return True
            
        except Exception as e:
            if not self._connection_error_logged:
                logger.warning(f"無法連接到 Neo4j: {str(e)}. 將使用降級模式。")
                self._connection_error_logged = True
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """斷開 Neo4j 連接"""
        if self.driver:
            await self.driver.close()
            self.driver = None
            self.is_connected = False
            logger.info("已斷開 Neo4j 連接")
    
    async def execute_query(
        self, 
        query: str, 
        parameters: Optional[Dict[str, Any]] = None,
        fallback_result: Any = None
    ) -> Any:
        """
        執行 Neo4j 查詢，提供降級處理
        
        Args:
            query: Cypher 查詢語句
            parameters: 查詢參數
            fallback_result: 降級時的返回結果
            
        Returns:
            查詢結果或降級結果
        """
        if not self.is_connected:
            logger.debug(f"Neo4j 不可用，返回降級結果")
            return fallback_result
            
        try:
            async with self.driver.session(database=self.database) as session:
                result = await session.run(query, parameters or {})
                return await result.data()
        except Exception as e:
            logger.error(f"執行 Neo4j 查詢失敗: {str(e)}")
            return fallback_result
    
    async def check_connection(self) -> bool:
        """檢查 Neo4j 連接狀態"""
        if not self.is_available or not self.driver:
            return False
            
        try:
            async with self.driver.session(database=self.database) as session:
                await session.run("RETURN 1")
            return True
        except Exception:
            self.is_connected = False
            return False
    
    def requires_neo4j(self, fallback_func=None):
        """
        裝飾器：要求 Neo4j 可用，否則執行降級函數
        
        Args:
            fallback_func: 降級函數
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                if self.is_connected:
                    return await func(*args, **kwargs)
                elif fallback_func:
                    logger.debug(f"{func.__name__} 降級到備用實現")
                    return await fallback_func(*args, **kwargs)
                else:
                    logger.warning(f"{func.__name__} 需要 Neo4j 但不可用")
                    return None
            return wrapper
        return decorator


# 全局 Neo4j 適配器實例
neo4j_adapter = Neo4jAdapter()


async def initialize_neo4j():
    """初始化 Neo4j 連接"""
    return await neo4j_adapter.connect()


async def shutdown_neo4j():
    """關閉 Neo4j 連接"""
    await neo4j_adapter.disconnect()


def is_neo4j_available() -> bool:
    """檢查 Neo4j 是否可用"""
    return neo4j_adapter.is_connected


async def execute_cypher(
    query: str,
    parameters: Optional[Dict[str, Any]] = None,
    fallback_result: Any = None
) -> Any:
    """
    執行 Cypher 查詢的便捷函數
    
    Args:
        query: Cypher 查詢語句
        parameters: 查詢參數
        fallback_result: 降級時的返回結果
        
    Returns:
        查詢結果或降級結果
    """
    return await neo4j_adapter.execute_query(query, parameters, fallback_result)


# 降級策略函數
async def fallback_graph_query(alert_id: str) -> Dict[str, Any]:
    """圖形查詢的降級實現"""
    return {
        "status": "degraded",
        "message": "Graph database unavailable, using fallback",
        "alert_id": alert_id,
        "entities": [],
        "relationships": []
    }


async def fallback_persist_entities(entities: List[Dict], relationships: List[Dict]) -> Dict[str, Any]:
    """實體持久化的降級實現"""
    logger.info(f"降級模式：無法持久化 {len(entities)} 個實體和 {len(relationships)} 個關係")
    return {
        "status": "degraded",
        "message": "Graph persistence unavailable",
        "entities_count": len(entities),
        "relationships_count": len(relationships),
        "persisted": False
    }


# 使用示例
@neo4j_adapter.requires_neo4j(fallback_func=fallback_graph_query)
async def query_alert_graph(alert_id: str) -> Dict[str, Any]:
    """查詢警報的圖形數據"""
    query = """
    MATCH (a:Alert {alert_id: $alert_id})-[r]-(e)
    RETURN a, r, e
    LIMIT 50
    """
    return await execute_cypher(query, {"alert_id": alert_id})


@neo4j_adapter.requires_neo4j(fallback_func=fallback_persist_entities)
async def persist_graph_data(entities: List[Dict], relationships: List[Dict]) -> Dict[str, Any]:
    """持久化圖形數據"""
    # 實際的持久化邏輯
    pass