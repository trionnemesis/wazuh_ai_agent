"""Neo4j graph database implementation."""
import asyncio
from typing import Dict, Any, List, Optional
from neo4j import AsyncGraphDatabase
import structlog

from ..core.interfaces import IGraphDatabase
from ..core.config import settings

logger = structlog.get_logger()


class Neo4jDatabase(IGraphDatabase):
    """Neo4j graph database implementation for GraphRAG."""
    
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
        """Connect to Neo4j database."""
        try:
            self.driver = AsyncGraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password)
            )
            
            # Test connection
            async with self.driver.session() as session:
                await session.run("RETURN 1")
                
            logger.info("Connected to Neo4j", uri=self.uri)
            
            # Create indexes for performance
            await self._create_indexes()
            
        except Exception as e:
            logger.error("Failed to connect to Neo4j", error=str(e))
            raise
            
    async def disconnect(self) -> None:
        """Disconnect from Neo4j database."""
        if self.driver:
            await self.driver.close()
            logger.info("Disconnected from Neo4j")
            
    async def create_node(
        self,
        node_type: str,
        properties: Dict[str, Any]
    ) -> str:
        """Create a node in the graph."""
        try:
            async with self.driver.session() as session:
                # Create node with merge to avoid duplicates
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
            logger.error("Failed to create node", 
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
        """Create a relationship between nodes."""
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
            logger.error("Failed to create relationship",
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
        """Find paths in the graph."""
        try:
            async with self.driver.session() as session:
                if end_node:
                    # Find specific paths between nodes
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
                    # Find all paths from start node
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
                    
                    # Extract nodes and relationships
                    for i, node in enumerate(path.nodes):
                        node_data = {
                            "id": str(node.id),
                            "labels": list(node.labels),
                            "properties": dict(node)
                        }
                        path_data.append(node_data)
                        
                        # Add relationship if not last node
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
            logger.error("Failed to find paths",
                        start_node=start_node,
                        error=str(e))
            return []
            
    async def query(
        self,
        cypher: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Execute a Cypher query."""
        try:
            async with self.driver.session() as session:
                result = await session.run(cypher, parameters or {})
                
                records = []
                async for record in result:
                    records.append(dict(record))
                    
                return records
                
        except Exception as e:
            logger.error("Cypher query failed",
                        query=cypher[:100],
                        error=str(e))
            raise
            
    async def _create_indexes(self) -> None:
        """Create indexes for better performance."""
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
                    logger.warning("Index creation failed",
                                 query=index_query,
                                 error=str(e))
                                 
    async def find_attack_chains(
        self,
        ioc_value: str,
        max_hops: int = 5
    ) -> List[Dict[str, Any]]:
        """Find potential attack chains involving an IOC."""
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
            logger.error("Failed to find attack chains", error=str(e))
            return []
            
    def _calculate_chain_risk(self, chain_result: Dict[str, Any]) -> float:
        """Calculate risk score for an attack chain."""
        risk_score = 0.0
        
        # Longer chains indicate more complex attacks
        risk_score += len(chain_result["node_types"]) * 0.1
        
        # Certain relationship types are more concerning
        high_risk_rels = ["EXECUTED", "DOWNLOADED", "PRIVILEGE_ESCALATED"]
        for rel in chain_result["rel_types"]:
            if rel in high_risk_rels:
                risk_score += 0.2
                
        # Certain node sequences indicate known attack patterns
        node_seq = "->".join(chain_result["node_types"])
        if "ip_address->host->user_account" in node_seq:
            risk_score += 0.3  # Lateral movement pattern
        if "file->host->ip_address" in node_seq:
            risk_score += 0.3  # Data exfiltration pattern
            
        return min(risk_score, 1.0)
