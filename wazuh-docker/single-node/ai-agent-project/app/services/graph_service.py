"""
圖形服務模組
封裝所有與 Neo4j 圖形資料庫的互動
"""

import logging
import uuid
import re
from typing import List, Dict, Any
from datetime import datetime
from dateutil import parser

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

async def extract_graph_entities(alert: Dict[str, Any], context_data: Dict[str, Any], analysis_result: str) -> List[Dict[str, Any]]:
    """
    從警報、上下文資料和分析結果中提取圖形實體
    
    Args:
        alert: 原始警報資料
        context_data: 上下文關聯資料
        analysis_result: LLM 分析結果
    
    Returns:
        提取的圖形實體列表
    """
    entities = []
    alert_source = alert.get('_source', {})
    
    # 1. 警報實體 (Alert Entity)
    alert_entity = {
        'type': 'Alert',
        'id': alert['_id'],
        'properties': {
            'alert_id': alert['_id'],
            'timestamp': alert_source.get('timestamp'),
            'rule_id': alert_source.get('rule', {}).get('id'),
            'rule_description': alert_source.get('rule', {}).get('description'),
            'rule_level': alert_source.get('rule', {}).get('level'),
            'rule_groups': alert_source.get('rule', {}).get('groups', []),
            'risk_level': _extract_risk_level_from_analysis(analysis_result),
            'triage_score': _calculate_triage_score(alert_source, analysis_result)
        }
    }
    entities.append(alert_entity)
    
    # 2. 主機實體 (Host Entity)
    agent = alert_source.get('agent', {})
    if agent.get('id') or agent.get('name'):
        host_entity = {
            'type': 'Host',
            'id': f"host_{agent.get('id', agent.get('name', 'unknown'))}",
            'properties': {
                'agent_id': agent.get('id'),
                'agent_name': agent.get('name'),
                'agent_ip': agent.get('ip'),
                'operating_system': _extract_os_info(alert_source)
            }
        }
        entities.append(host_entity)
    
    # 3. IP 位址實體 (IP Address Entities)
    ip_addresses = _extract_ip_addresses(alert_source)
    for ip_info in ip_addresses:
        ip_entity = {
            'type': 'IPAddress',
            'id': f"ip_{ip_info['address']}",
            'properties': {
                'address': ip_info['address'],
                'type': ip_info['type'],  # source, destination, internal
                'geolocation': ip_info.get('geo'),
                'is_private': _is_private_ip(ip_info['address'])
            }
        }
        entities.append(ip_entity)
    
    # 4. 使用者實體 (User Entities)
    users = _extract_user_info(alert_source)
    for user_info in users:
        user_entity = {
            'type': 'User',
            'id': f"user_{user_info['name']}",
            'properties': {
                'username': user_info['name'],
                'user_type': user_info.get('type', 'unknown'),
                'authentication_method': user_info.get('auth_method')
            }
        }
        entities.append(user_entity)
    
    # 5. 程序實體 (Process Entities)
    processes = _extract_process_info(alert_source, context_data)
    for process_info in processes:
        process_entity = {
            'type': 'Process',
            'id': f"process_{process_info.get('pid', 'unknown')}_{process_info.get('name', 'unknown')}",
            'properties': {
                'process_name': process_info.get('name'),
                'process_id': process_info.get('pid'),
                'command_line': process_info.get('cmdline'),
                'parent_process': process_info.get('ppid'),
                'hash': process_info.get('hash')
            }
        }
        entities.append(process_entity)
    
    # 6. 檔案實體 (File Entities)
    files = _extract_file_info(alert_source)
    for file_info in files:
        file_entity = {
            'type': 'File',
            'id': f"file_{hash(file_info['path'])}",
            'properties': {
                'file_path': file_info['path'],
                'file_name': file_info.get('name'),
                'file_size': file_info.get('size'),
                'file_hash': file_info.get('hash'),
                'file_permissions': file_info.get('permissions')
            }
        }
        entities.append(file_entity)
    
    # 7. 威脅實體 (從分析結果提取)
    threat_indicators = _extract_threat_indicators(analysis_result)
    for threat in threat_indicators:
        threat_entity = {
            'type': 'ThreatIndicator',
            'id': f"threat_{uuid.uuid4().hex[:8]}",
            'properties': {
                'indicator_type': threat['type'],
                'indicator_value': threat['value'],
                'confidence': threat.get('confidence', 0.5),
                'mitre_technique': threat.get('mitre_technique')
            }
        }
        entities.append(threat_entity)
    
    logger.info(f"Extracted {len(entities)} entities: {dict(zip(*zip(*[(e['type'], 1) for e in entities])))}")
    return entities

async def execute_graph_retrieval(cypher_queries: List[Dict[str, Any]], alert: Dict[str, Any]) -> Dict[str, Any]:
    """
    Graph-Native 檢索器：執行 Cypher 查詢來檢索相關的圖形子網
    這是 GraphRAG 的核心檢索引擎，取代傳統的向量與關鍵字搜尋
    
    Args:
        cypher_queries: 從 Decision Engine 生成的 Cypher 查詢任務列表
        alert: 當前警報資料
        
    Returns:
        Dictionary 包含檢索到的圖形子網和結構化上下文
    """
    from ..services.neo4j_service import get_neo4j_driver
    from ..services.metrics import api_call_duration, api_errors_total
    import asyncio
    
    logger.info(f"🔗 GRAPH-NATIVE RETRIEVAL: Processing {len(cypher_queries)} Cypher queries")
    
    context_data = {
        'attack_paths': [],           # 攻擊路徑子圖
        'lateral_movement': [],       # 橫向移動模式
        'temporal_sequences': [],     # 時間序列關聯
        'ip_reputation': [],          # IP 信譽圖
        'user_behavior': [],          # 使用者行為圖
        'process_chains': [],         # 程序執行鏈
        'file_interactions': [],      # 檔案交互圖
        'network_topology': [],       # 網路拓撲
        'threat_landscape': [],       # 威脅全景
        'correlation_graph': []       # 相關性圖
    }
    
    neo4j_driver = get_neo4j_driver()
    if not neo4j_driver:
        logger.warning("Neo4j driver not available - falling back to traditional retrieval")
        # 降級到傳統檢索
        return await _fallback_to_traditional_retrieval(alert)
    
    # 排序查詢以優化執行順序
    sorted_queries = sorted(cypher_queries, key=lambda x: {
        'critical': 0, 'high': 1, 'medium': 2, 'low': 3
    }.get(x.get('priority', 'medium'), 2))
    
    alert_id = alert.get('_id', 'unknown')
    
    async with neo4j_driver.session() as session:
        # 改為並行執行所有查詢
        async def execute_single_query(query_spec):
            """執行單個 Cypher 查詢"""
            query_name = query_spec.get('name', 'unknown')
            purpose = query_spec.get('purpose', '')
            cypher_template = query_spec.get('cypher_template', '')
            parameters = query_spec.get('parameters', {})
            parameters['alert_id'] = alert_id
            
            try:
                neo4j_start = datetime.now()
                result = await session.run(cypher_template, parameters)
                records = await result.data()
                neo4j_duration = (datetime.now() - neo4j_start).total_seconds()
                api_call_duration.labels(stage='neo4j').observe(neo4j_duration)
                
                logger.info(f"   ✅ {query_name}: {purpose} - {len(records)} results ({neo4j_duration:.3f}s)")
                return {
                    'name': query_name,
                    'records': records,
                    'duration': neo4j_duration
                }
            except Exception as e:
                api_errors_total.labels(stage='neo4j').inc()
                logger.error(f"   ❌ {query_name} failed: {str(e)}")
                return {
                    'name': query_name,
                    'records': [],
                    'error': str(e)
                }
        
        # 並行執行所有查詢
        logger.info(f"   🚀 Executing {len(sorted_queries)} Cypher queries in parallel...")
        query_results = await asyncio.gather(
            *[execute_single_query(q) for q in sorted_queries],
            return_exceptions=False
        )
        
        # 處理查詢結果
        for result in query_results:
            if result and not result.get('error'):
                await _categorize_graph_results(
                    result['name'], 
                    result['records'], 
                    context_data
                )
    
    # 生成檢索摘要
    total_components = sum(len(results) for results in context_data.values())
    logger.info(f"📊 GRAPH RETRIEVAL SUMMARY: {total_components} total graph components")
    for category, results in context_data.items():
        if results:
            logger.info(f"   {category}: {len(results)} components")
    
    return context_data

async def _categorize_graph_results(query_name: str, records: List[Dict], context_data: Dict[str, Any]):
    """
    根據查詢類型將圖形結果分類到適當的上下文類別中
    
    Args:
        query_name: 查詢名稱（攻擊路徑、橫向移動等）
        records: Cypher 查詢返回的記錄
        context_data: 要更新的上下文資料字典
    """
    # 根據查詢名稱映射到上下文類別
    category_mapping = {
        'lateral_movement_detection': 'lateral_movement',
        'ip_activity_pattern': 'ip_reputation',
        'host_attack_timeline': 'temporal_sequences',
        'attack_path_discovery': 'attack_paths',
        'user_behavior_analysis': 'user_behavior',
        'process_chain_analysis': 'process_chains',
        'file_access_pattern': 'file_interactions',
        'network_flow_analysis': 'network_topology',
        'threat_correlation': 'correlation_graph',
        'threat_actor_profile': 'threat_landscape'
    }
    
    category = category_mapping.get(query_name, 'correlation_graph')
    
    # 將記錄添加到相應類別
    if category in context_data:
        context_data[category].extend(records)
    else:
        logger.warning(f"Unknown query category: {query_name}")

async def _fallback_to_traditional_retrieval(alert: Dict[str, Any]) -> Dict[str, Any]:
    """
    當 Neo4j 不可用時的降級方案
    返回空的圖形上下文，讓系統使用傳統檢索方法
    
    Args:
        alert: 警報資料
        
    Returns:
        空的圖形上下文字典
    """
    return {
        'attack_paths': [],
        'lateral_movement': [],
        'temporal_sequences': [],
        'ip_reputation': [],
        'user_behavior': [],
        'process_chains': [],
        'file_interactions': [],
        'network_topology': [],
        'threat_landscape': [],
        'correlation_graph': []
    }

async def build_graph_relationships(entities: List[Dict[str, Any]], alert: Dict[str, Any], context_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    根據實體和上下文資料建立圖形關係
    
    Args:
        entities: 提取的實體列表
        alert: 原始警報資料
        context_data: 上下文關聯資料
    
    Returns:
        實體間的關係列表
    """
    relationships = []
    entity_by_id = {entity['id']: entity for entity in entities}
    entity_by_type = {}
    
    # 按類型組織實體
    for entity in entities:
        entity_type = entity['type']
        if entity_type not in entity_by_type:
            entity_by_type[entity_type] = []
        entity_by_type[entity_type].append(entity)
    
    # 1. 警報觸發關係 (Alert -> Host)
    alert_entities = entity_by_type.get('Alert', [])
    host_entities = entity_by_type.get('Host', [])
    
    for alert_entity in alert_entities:
        for host_entity in host_entities:
            relationship = {
                'type': 'TRIGGERED_ON',
                'source_id': alert_entity['id'],
                'target_id': host_entity['id'],
                'properties': {
                    'timestamp': alert.get('_source', {}).get('timestamp'),
                    'severity': alert.get('_source', {}).get('rule', {}).get('level')
                }
            }
            relationships.append(relationship)
    
    # 2. 來源 IP 關係 (Alert -> IPAddress)
    ip_entities = entity_by_type.get('IPAddress', [])
    for alert_entity in alert_entities:
        for ip_entity in ip_entities:
            if ip_entity['properties'].get('type') == 'source':
                relationship = {
                    'type': 'HAS_SOURCE_IP',
                    'source_id': alert_entity['id'],
                    'target_id': ip_entity['id'],
                    'properties': {
                        'timestamp': alert.get('_source', {}).get('timestamp')
                    }
                }
                relationships.append(relationship)
    
    # 3. 使用者參與關係 (Alert -> User)
    user_entities = entity_by_type.get('User', [])
    for alert_entity in alert_entities:
        for user_entity in user_entities:
            relationship = {
                'type': 'INVOLVES_USER',
                'source_id': alert_entity['id'],
                'target_id': user_entity['id'],
                'properties': {
                    'timestamp': alert.get('_source', {}).get('timestamp'),
                    'action_type': _determine_user_action_type(alert)
                }
            }
            relationships.append(relationship)
    
    # 4. 程序執行關係 (Alert -> Process)
    process_entities = entity_by_type.get('Process', [])
    for alert_entity in alert_entities:
        for process_entity in process_entities:
            relationship = {
                'type': 'INVOLVES_PROCESS',
                'source_id': alert_entity['id'],
                'target_id': process_entity['id'],
                'properties': {
                    'timestamp': alert.get('_source', {}).get('timestamp')
                }
            }
            relationships.append(relationship)
    
    # 5. 檔案存取關係 (Alert -> File)
    file_entities = entity_by_type.get('File', [])
    for alert_entity in alert_entities:
        for file_entity in file_entities:
            relationship = {
                'type': 'ACCESSES_FILE',
                'source_id': alert_entity['id'],
                'target_id': file_entity['id'],
                'properties': {
                    'timestamp': alert.get('_source', {}).get('timestamp'),
                    'access_type': _determine_file_access_type(alert)
                }
            }
            relationships.append(relationship)
    
    # 6. 類似警報關係 (基於上下文資料)
    similar_alerts = context_data.get('similar_alerts', [])
    for similar_alert in similar_alerts[:5]:  # 限制關係數量
        similar_alert_id = similar_alert.get('_id')
        if similar_alert_id:
            for alert_entity in alert_entities:
                relationship = {
                    'type': 'SIMILAR_TO',
                    'source_id': alert_entity['id'],
                    'target_id': f"alert_{similar_alert_id}",  # 假設該警報已在圖中
                    'properties': {
                        'similarity_score': similar_alert.get('_score', 0.0),
                        'correlation_type': 'vector_similarity'
                    }
                }
                relationships.append(relationship)
    
    # 7. 時間序列關係 (Temporal Relationships)
    # 根據時間戳建立 PRECEDES 關係
    if len(alert_entities) > 1:
        sorted_alerts = sorted(alert_entities, key=lambda x: x['properties'].get('timestamp', ''))
        for i in range(len(sorted_alerts) - 1):
            relationship = {
                'type': 'PRECEDES',
                'source_id': sorted_alerts[i]['id'],
                'target_id': sorted_alerts[i + 1]['id'],
                'properties': {
                    'time_difference': _calculate_time_difference(
                        sorted_alerts[i]['properties'].get('timestamp'),
                        sorted_alerts[i + 1]['properties'].get('timestamp')
                    )
                }
            }
            relationships.append(relationship)
    
    logger.info(f"Built {len(relationships)} relationships")
    return relationships

async def persist_to_graph_database(entities: List[Dict[str, Any]], relationships: List[Dict[str, Any]], alert_id: str) -> Dict[str, Any]:
    """
    將實體和關係持久化到 Neo4j 圖形資料庫
    
    Args:
        entities: 要存儲的實體列表
        relationships: 要存儲的關係列表
        alert_id: 警報 ID
    
    Returns:
        持久化結果，包含成功狀態和統計資訊
    """
    from ..services.neo4j_service import get_neo4j_driver
    
    neo4j_driver = get_neo4j_driver()
    if not neo4j_driver:
        return {
            'success': False,
            'error': 'Neo4j driver not available',
            'nodes_created': 0,
            'relationships_created': 0
        }
    
    try:
        async with neo4j_driver.session() as session:
            # 存儲節點
            nodes_created = 0
            node_ids = []
            
            for entity in entities:
                # 使用 MERGE 來避免重複節點
                cypher_query = f"""
                MERGE (n:{entity['type']} {{id: $entity_id}})
                SET n += $properties
                RETURN n.id as node_id
                """
                
                result = await session.run(
                    cypher_query,
                    entity_id=entity['id'],
                    properties=entity['properties']
                )
                
                record = await result.single()
                if record:
                    node_ids.append(record['node_id'])
                    nodes_created += 1
            
            # 存儲關係
            relationships_created = 0
            
            for relationship in relationships:
                # 使用 MERGE 來避免重複關係
                cypher_query = f"""
                MATCH (source {{id: $source_id}})
                MATCH (target {{id: $target_id}})
                MERGE (source)-[r:{relationship['type']}]->(target)
                SET r += $properties
                RETURN r
                """
                
                result = await session.run(
                    cypher_query,
                    source_id=relationship['source_id'],
                    target_id=relationship['target_id'],
                    properties=relationship.get('properties', {})
                )
                
                if await result.peek():
                    relationships_created += 1
            
            # 建立索引 (如果不存在)
            index_queries = [
                "CREATE INDEX alert_timestamp_idx IF NOT EXISTS FOR (a:Alert) ON (a.timestamp)",
                "CREATE INDEX host_agent_id_idx IF NOT EXISTS FOR (h:Host) ON (h.agent_id)",
                "CREATE INDEX ip_address_idx IF NOT EXISTS FOR (i:IPAddress) ON (i.address)",
                "CREATE INDEX user_name_idx IF NOT EXISTS FOR (u:User) ON (u.username)"
            ]
            
            for index_query in index_queries:
                await session.run(index_query)
            
            return {
                'success': True,
                'nodes_created': nodes_created,
                'relationships_created': relationships_created,
                'node_ids': node_ids,
                'timestamp': datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Graph persistence error: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'nodes_created': 0,
            'relationships_created': 0
        }

# ==================== 輔助函數 ====================

def _determine_user_action_type(alert: Dict) -> str:
    """確定使用者動作類型"""
    rule_desc = alert.get('_source', {}).get('rule', {}).get('description', '').lower()
    
    if 'login' in rule_desc or 'authentication' in rule_desc:
        return 'authentication'
    elif 'ssh' in rule_desc:
        return 'remote_access'
    elif 'file' in rule_desc:
        return 'file_access'
    else:
        return 'unknown'

def _determine_file_access_type(alert: Dict) -> str:
    """確定檔案存取類型"""
    rule_desc = alert.get('_source', {}).get('rule', {}).get('description', '').lower()
    
    if 'write' in rule_desc or 'modify' in rule_desc:
        return 'write'
    elif 'read' in rule_desc:
        return 'read'
    elif 'delete' in rule_desc:
        return 'delete'
    else:
        return 'access'

def _calculate_time_difference(timestamp1: str, timestamp2: str) -> int:
    """計算兩個時間戳之間的差異（秒）"""
    try:
        dt1 = parser.parse(timestamp1)
        dt2 = parser.parse(timestamp2)
        return int(abs((dt2 - dt1).total_seconds()))
    except:
        return 0