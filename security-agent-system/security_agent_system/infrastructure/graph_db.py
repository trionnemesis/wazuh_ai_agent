"""Neo4j 圖形資料庫實作。"""
import asyncio
from typing import Dict, Any, List, Optional
from neo4j import AsyncGraphDatabase
import structlog

from ..core.interfaces import IGraphDatabase
from ..core.config import settings

logger = structlog.get_logger()


class Neo4jDatabase(IGraphDatabase):
    """用於 GraphRAG 的 Neo4j 圖形資料庫實作。"""
    
    def __init__(
        self,
        uri: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None
    ):
        self.uri = uri or settings.neo4j_uri
        self.username = username or settings.neo4j_username
        self.password = password or settings.neo4j_password
        self.driver = None
        
    async def connect(self) -> None:
        """連接到 Neo4j 資料庫。"""
        try:
            self.driver = AsyncGraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password)
            )
            
            # 測試連線
            async with self.driver.session() as session:
                await session.run("RETURN 1")
                
            logger.info("已連接到 Neo4j", uri=self.uri)
            
            # 建立索引以提升效能
            await self._create_indexes()
            
        except Exception as e:
            logger.error("連接到 Neo4j 失敗", error=str(e))
            raise
            
    async def disconnect(self) -> None:
        """從 Neo4j 資料庫斷開連線。"""
        if self.driver:
            await self.driver.close()
            logger.info("已從 Neo4j 斷開連線")
            
    async def create_node(
        self,
        node_type: str,
        properties: Dict[str, Any]
    ) -> str:
        """在圖形中建立一個節點。"""
        try:
            async with self.driver.session() as session:
                # 使用 MERGE 建立節點以避免重複
                query = f"""
                MERGE (n:{node_type} {{value: $value}})
                ON CREATE SET n += $properties, n.created_at = datetime()
                ON MATCH SET n.last_seen = datetime(), n.alert_count = n.alert_count + 1
                RETURN id(n) as node_id
                """
                
                result = await session.run(
                    query,
                    value=properties.get("value"),
                    properties=properties
                )
                
                record = await result.single()
                return str(record["node_id"])
                
        except Exception as e:
            logger.error("建立節點失敗",
                        node_type=node_type,
                        error=str(e))
            raise
            
    async def create_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
        properties: Optional[Dict[str, Any]] = None
    ) -> str:
        """在節點之間建立關係。"""
        try:
            async with self.driver.session() as session:
                query = f"""
                MATCH (a) WHERE id(a) = $source_id
                MATCH (b) WHERE id(b) = $target_id
                MERGE (a)-[r:{relationship_type}]->(b)
                ON CREATE SET r += $properties, r.created_at = datetime()
                ON MATCH SET r.last_seen = datetime(), r.count = r.count + 1
                RETURN id(r) as rel_id
                """
                
                result = await session.run(
                    query,
                    source_id=int(source_id),
                    target_id=int(target_id),
                    properties=properties or {}
                )
                
                record = await result.single()
                return str(record["rel_id"])
                
        except Exception as e:
            logger.error("建立關係失敗",
                        source_id=source_id,
                        target_id=target_id,
                        relationship_type=relationship_type,
                        error=str(e))
            raise
            
    async def find_paths(
        self,
        start_node: str,
        end_node: Optional[str] = None,
        max_depth: int = 3
    ) -> List[List[Dict[str, Any]]]:
        """在圖形中尋找路徑。"""
        try:
            async with self.driver.session() as session:
                if end_node:
                    # 尋找節點之間的特定路徑
                    query = """
                    MATCH path = (start)-[*1..$max_depth]-(end)
                    WHERE id(start) = $start_id AND id(end) = $end_id
                    RETURN path
                    LIMIT 10
                    """
                    params = {
                        "start_id": int(start_node),
                        "end_id": int(end_node),
                        "max_depth": max_depth
                    }
                else:
                    # 尋找從起始節點出發的所有路徑
                    query = """
                    MATCH path = (start)-[*1..$max_depth]-(end)
                    WHERE id(start) = $start_id
                    AND id(start) <> id(end)
                    RETURN path
                    LIMIT 20
                    """
                    params = {
                        "start_id": int(start_node),
                        "max_depth": max_depth
                    }
                    
                result = await session.run(query, params)
                
                paths = []
                async for record in result:
                    path = record["path"]
                    path_data = []
                    
                    # 提取節點和關係
                    for i, node in enumerate(path.nodes):
                        node_data = {
                            "id": str(node.id),
                            "labels": list(node.labels),
                            "properties": dict(node)
                        }
                        path_data.append(node_data)
                        
                        # 如果不是最後一個節點，則新增關係
                        if i < len(path.relationships):
                            rel = path.relationships[i]
                            rel_data = {
                                "type": "relationship",
                                "relationship_type": rel.type,
                                "properties": dict(rel)
                            }
                            path_data.append(rel_data)
                            
                    paths.append(path_data)
                    
                return paths
                
        except Exception as e:
            logger.error("尋找路徑失敗",
                        start_node=start_node,
                        error=str(e))
            return []
            
    async def query(
        self,
        cypher: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """執行一個 Cypher 查詢。"""
        try:
            async with self.driver.session() as session:
                result = await session.run(cypher, parameters or {})
                
                records = []
                async for record in result:
                    records.append(dict(record))
                    
                return records
                
        except Exception as e:
            logger.error("Cypher 查詢失敗",
                        query=cypher[:100],
                        error=str(e))
            raise
            
    async def _create_indexes(self) -> None:
        """建立索引以提升效能。"""
        indexes = [
            "CREATE INDEX IF NOT EXISTS FOR (n:ip_address) ON (n.value)",
            "CREATE INDEX IF NOT EXISTS FOR (n:host) ON (n.value)",
            "CREATE INDEX IF NOT EXISTS FOR (n:user_account) ON (n.value)",
            "CREATE INDEX IF NOT EXISTS FOR (n:file_hash) ON (n.value)",
            "CREATE INDEX IF NOT EXISTS FOR (n:alert) ON (n.alert_id)",
            "CREATE INDEX IF NOT EXISTS FOR (n:campaign) ON (n.campaign_id)"
        ]
        
        async with self.driver.session() as session:
            for index_query in indexes:
                try:
                    await session.run(index_query)
                except Exception as e:
                    logger.warning("索引建立失敗",
                                 query=index_query,
                                 error=str(e))
                                 
    async def find_attack_chains(
        self,
        ioc_value: str,
        max_hops: int = 5
    ) -> List[Dict[str, Any]]:
        """尋找涉及 IOC 的潛在攻擊鏈。"""
        query = """
        MATCH (ioc {value: $ioc_value})
        CALL apoc.path.expandConfig(ioc, {
            maxLevel: $max_hops,
            relationshipFilter: 'CONNECTS_TO|ACCESSED|EXECUTED|DOWNLOADED',
            labelFilter: '+ip_address|+host|+user_account|+file'
        })
        YIELD path
        WHERE length(path) >= 2
        RETURN path, 
               [n in nodes(path) | labels(n)[0]] as node_types,
               [r in relationships(path) | type(r)] as rel_types
        LIMIT 10
        """
        
        try:
            results = await self.query(
                query,
                {"ioc_value": ioc_value, "max_hops": max_hops}
            )
            
            attack_chains = []
            for result in results:
                chain = {
                    "length": len(result["node_types"]),
                    "node_sequence": result["node_types"],
                    "relationship_sequence": result["rel_types"],
                    "risk_score": self._calculate_chain_risk(result)
                }
                attack_chains.append(chain)
                
            return sorted(attack_chains, key=lambda x: x["risk_score"], reverse=True)
            
        except Exception as e:
            logger.error("尋找攻擊鏈失敗", error=str(e))
            return []
            
    def _calculate_chain_risk(self, chain_result: Dict[str, Any]) -> float:
        """計算攻擊鏈的風險分數。"""
        risk_score = 0.0
        
        # 較長的鏈表示較複雜的攻擊
        risk_score += len(chain_result["node_types"]) * 0.1
        
        # 某些關係類型更值得關注
        high_risk_rels = ["EXECUTED", "DOWNLOADED", "PRIVILEGE_ESCALATED"]
        for rel in chain_result["rel_types"]:
            if rel in high_risk_rels:
                risk_score += 0.2
                
        # 某些節點序列表示已知的攻擊模式
        node_seq = "->".join(chain_result["node_types"])
        if "ip_address->host->user_account" in node_seq:
            risk_score += 0.3  # 橫向移動模式
        if "file->host->ip_address" in node_seq:
            risk_score += 0.3  # 資料外洩模式
            
        return min(risk_score, 1.0)