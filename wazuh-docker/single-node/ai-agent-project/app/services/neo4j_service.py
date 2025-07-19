"""
Neo4j 服務模組
集中管理 Neo4j 驅動程式和圖形資料庫操作
"""

import logging
from typing import Optional, List, Dict, Any

from ..core.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

logger = logging.getLogger(__name__)

# 檢查 Neo4j 是否可用
try:
    from neo4j import AsyncGraphDatabase, AsyncDriver
    NEO4J_AVAILABLE = True
except ImportError:
    logger.warning("Neo4j 驅動程式不可用。圖形持久化功能將被停用。")
    NEO4J_AVAILABLE = False
    AsyncGraphDatabase = None
    AsyncDriver = None

# 全域 Neo4j 驅動程式實例
_driver: Optional[AsyncDriver] = None

def get_neo4j_driver() -> Optional[AsyncDriver]:
    """
    獲取 Neo4j 驅動程式實例（單例模式）
    
    Returns:
        Optional[AsyncDriver]: Neo4j 驅動程式，如果不可用則返回 None
    """
    global _driver
    
    if not NEO4J_AVAILABLE:
        return None
    
    if _driver is None:
        try:
            _driver = AsyncGraphDatabase.driver(
                NEO4J_URI,
                auth=(NEO4J_USER, NEO4J_PASSWORD)
            )
            logger.info(f"Neo4j 驅動程式已初始化: {NEO4J_URI}")
        except Exception as e:
            logger.error(f"Neo4j 驅動程式初始化失敗: {str(e)}")
            return None
    
    return _driver

async def close_neo4j_driver():
    """關閉 Neo4j 驅動程式"""
    global _driver
    
    if _driver is not None:
        await _driver.close()
        _driver = None
        logger.info("Neo4j 驅動程式已關閉")

async def check_neo4j_connection() -> bool:
    """
    檢查 Neo4j 連接是否正常
    
    Returns:
        bool: 連接是否成功
    """
    driver = get_neo4j_driver()
    if not driver:
        return False
    
    try:
        async with driver.session() as session:
            result = await session.run("RETURN 1 as test")
            await result.single()
        return True
    except Exception as e:
        logger.error(f"Neo4j 連接檢查失敗: {str(e)}")
        return False

async def execute_cypher_query(query: str, parameters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """
    執行 Cypher 查詢
    
    Args:
        query: Cypher 查詢語句
        parameters: 查詢參數
        
    Returns:
        List[Dict]: 查詢結果列表
    """
    driver = get_neo4j_driver()
    if not driver:
        logger.warning("Neo4j 驅動程式不可用")
        return []
    
    try:
        async with driver.session() as session:
            result = await session.run(query, parameters or {})
            records = []
            async for record in result:
                records.append(dict(record))
            return records
    except Exception as e:
        logger.error(f"執行 Cypher 查詢失敗: {str(e)}")
        return []

async def create_constraint(label: str, property_name: str) -> bool:
    """
    創建唯一性約束
    
    Args:
        label: 節點標籤
        property_name: 屬性名稱
        
    Returns:
        bool: 是否成功
    """
    driver = get_neo4j_driver()
    if not driver:
        return False
    
    try:
        async with driver.session() as session:
            query = f"""
            CREATE CONSTRAINT IF NOT EXISTS
            FOR (n:{label})
            REQUIRE n.{property_name} IS UNIQUE
            """
            await session.run(query)
            logger.info(f"創建約束成功: {label}.{property_name}")
            return True
    except Exception as e:
        logger.error(f"創建約束失敗: {str(e)}")
        return False

async def create_index(label: str, property_name: str) -> bool:
    """
    創建索引
    
    Args:
        label: 節點標籤
        property_name: 屬性名稱
        
    Returns:
        bool: 是否成功
    """
    driver = get_neo4j_driver()
    if not driver:
        return False
    
    try:
        async with driver.session() as session:
            query = f"""
            CREATE INDEX IF NOT EXISTS
            FOR (n:{label})
            ON (n.{property_name})
            """
            await session.run(query)
            logger.info(f"創建索引成功: {label}.{property_name}")
            return True
    except Exception as e:
        logger.error(f"創建索引失敗: {str(e)}")
        return False

async def batch_create_nodes(nodes: List[Dict[str, Any]]) -> int:
    """
    批量創建節點
    
    Args:
        nodes: 節點數據列表，每個節點包含 label 和 properties
        
    Returns:
        int: 創建的節點數量
    """
    driver = get_neo4j_driver()
    if not driver:
        return 0
    
    try:
        async with driver.session() as session:
            created_count = 0
            for node in nodes:
                query = f"""
                MERGE (n:{node['label']} {{id: $id}})
                SET n += $properties
                RETURN n
                """
                await session.run(query, {
                    'id': node['properties'].get('id'),
                    'properties': node['properties']
                })
                created_count += 1
            
            logger.info(f"批量創建 {created_count} 個節點")
            return created_count
    except Exception as e:
        logger.error(f"批量創建節點失敗: {str(e)}")
        return 0

async def batch_create_relationships(relationships: List[Dict[str, Any]]) -> int:
    """
    批量創建關係
    
    Args:
        relationships: 關係數據列表，每個關係包含 source, target, type 和 properties
        
    Returns:
        int: 創建的關係數量
    """
    driver = get_neo4j_driver()
    if not driver:
        return 0
    
    try:
        async with driver.session() as session:
            created_count = 0
            for rel in relationships:
                query = f"""
                MATCH (source {{id: $source_id}})
                MATCH (target {{id: $target_id}})
                MERGE (source)-[r:{rel['type']}]->(target)
                SET r += $properties
                RETURN r
                """
                await session.run(query, {
                    'source_id': rel['source'],
                    'target_id': rel['target'],
                    'properties': rel.get('properties', {})
                })
                created_count += 1
            
            logger.info(f"批量創建 {created_count} 個關係")
            return created_count
    except Exception as e:
        logger.error(f"批量創建關係失敗: {str(e)}")
        return 0