"""
決策服務模組
成為 Agentic AI 的 "大腦"，決定需要哪些資訊
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..services.llm_service import get_llm
from ..core.config import NEO4J_URI
from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)

# === 決策相關的提示詞模板 ===

# Stage 3: Agentic 上下文查詢決策提示詞
contextual_query_prompt = ChatPromptTemplate.from_template(
    """As an AI security analyst, analyze this alert and determine what contextual information 
    would be most valuable for a comprehensive threat assessment.

    Alert Summary: {alert_summary}

    Based on this alert, identify specific queries needed to gather contextual information.
    Consider temporal correlations, related processes, network patterns, and user behaviors.

    Your output should be a JSON array of query specifications. Each query should have:
    - type: One of ['vector_similarity', 'time_range', 'keyword', 'aggregation']
    - parameters: Specific parameters for that query type
    - rationale: Why this query is relevant

    Example format:
    [
        {{
            "type": "vector_similarity",
            "parameters": {{"k": 5}},
            "rationale": "Find similar historical alerts"
        }},
        {{
            "type": "time_range",
            "parameters": {{"field": "agent.name", "value": "server-01", "minutes": 30}},
            "rationale": "Check recent activity on the same host"
        }}
    ]

    Generate the query specifications:
    """
)

# GraphRAG 查詢決策提示詞
graph_query_prompt = ChatPromptTemplate.from_template(
    """You are a graph-based threat hunting specialist. Analyze this security alert and determine 
    what graph traversal patterns would reveal the most valuable threat intelligence.

    **Alert Summary:**
    {alert_summary}

    **Alert Context:**
    {alert_context}

    Generate Cypher query templates that explore:
    1. Attack paths and lateral movement
    2. Entity relationships (IPs, users, processes, files)
    3. Temporal attack sequences
    4. Common attack patterns

    Output a JSON array of query specifications:
    [
        {{
            "name": "lateral_movement_detection",
            "cypher_template": "MATCH path = (ip:IP {{address: $source_ip}})-[*1..3]-(host:Host) WHERE ...",
            "parameters": {{"source_ip": "extracted_value"}},
            "purpose": "Detect potential lateral movement from source IP"
        }}
    ]

    Focus on actionable intelligence that reveals attack patterns.
    Generate the Cypher query specifications:
    """
)

async def determine_contextual_queries(alert: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Stage 3: Agentic Context Correlation - 決定需要哪些上下文查詢
    
    使用 LLM 分析警報內容，智能決定需要收集哪些相關資訊，
    實現真正的 "Agentic" 行為模式。
    
    Args:
        alert: 原始警報資料
        
    Returns:
        List[Dict]: 查詢規格列表，每個包含查詢類型、參數和理由
    """
    try:
        # 提取警報摘要
        alert_summary = f"""
        Rule: {alert.get('rule', {}).get('description', 'N/A')}
        Level: {alert.get('rule', {}).get('level', 'N/A')}
        Agent: {alert.get('agent', {}).get('name', 'N/A')}
        Source IP: {alert.get('data', {}).get('srcip', 'N/A')}
        Event Type: {alert.get('decoder', {}).get('name', 'N/A')}
        """
        
        # 使用 LLM 決定查詢策略
        llm = get_llm()
        chain = contextual_query_prompt | llm
        
        response = await chain.ainvoke({"alert_summary": alert_summary})
        
        # 解析 LLM 回應
        import json
        try:
            # 嘗試從回應中提取 JSON
            content = response.content if hasattr(response, 'content') else str(response)
            
            # 尋找 JSON 陣列
            start_idx = content.find('[')
            end_idx = content.rfind(']') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = content[start_idx:end_idx]
                queries = json.loads(json_str)
                
                # 驗證並標準化查詢格式
                validated_queries = []
                for query in queries:
                    if isinstance(query, dict) and 'type' in query:
                        validated_queries.append(query)
                
                logger.info(f"🤖 Agentic Decision: Generated {len(validated_queries)} contextual queries")
                return validated_queries
                
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
        
        # 如果 LLM 解析失敗，返回預設查詢策略
        return _get_default_queries(alert)
        
    except Exception as e:
        logger.error(f"Error in determine_contextual_queries: {str(e)}")
        return _get_default_queries(alert)

async def determine_graph_queries(alert: Dict[str, Any], context_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    決定需要執行哪些圖形查詢來獲取威脅情報
    
    Args:
        alert: 警報資料
        context_data: 已收集的上下文資料
        
    Returns:
        List[Dict]: Cypher 查詢規格列表
    """
    if not NEO4J_URI:
        logger.warning("Neo4j 未配置，跳過圖形查詢生成")
        return []
    
    try:
        # 準備警報摘要和上下文
        alert_summary = _create_alert_summary(alert)
        alert_context = _create_alert_context(alert, context_data)
        
        # 使用 LLM 生成 Cypher 查詢
        llm = get_llm()
        chain = graph_query_prompt | llm
        
        response = await chain.ainvoke({
            "alert_summary": alert_summary,
            "alert_context": alert_context
        })
        
        # 解析回應
        queries = _parse_graph_queries(response)
        
        logger.info(f"📊 Generated {len(queries)} graph queries for threat hunting")
        return queries
        
    except Exception as e:
        logger.error(f"Error generating graph queries: {str(e)}")
        return _get_default_graph_queries(alert)

def _get_default_queries(alert: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    提供預設的查詢策略作為後備方案
    """
    queries = [
        {
            "type": "vector_similarity",
            "parameters": {"k": 5},
            "rationale": "Find similar historical alerts"
        }
    ]
    
    # 根據警報類型添加特定查詢
    if alert.get('agent', {}).get('name'):
        queries.append({
            "type": "time_range",
            "parameters": {
                "field": "agent.name",
                "value": alert['agent']['name'],
                "minutes": 30
            },
            "rationale": "Check recent activity on the same host"
        })
    
    if alert.get('data', {}).get('srcip'):
        queries.append({
            "type": "keyword",
            "parameters": {
                "field": "data.srcip",
                "value": alert['data']['srcip']
            },
            "rationale": "Track source IP activity"
        })
    
    return queries

def _create_alert_summary(alert: Dict[str, Any]) -> str:
    """創建警報摘要"""
    return f"""
    Rule: {alert.get('rule', {}).get('description', 'N/A')}
    Level: {alert.get('rule', {}).get('level', 'N/A')}
    Agent: {alert.get('agent', {}).get('name', 'N/A')}
    Source IP: {alert.get('data', {}).get('srcip', 'N/A')}
    Destination IP: {alert.get('data', {}).get('dstip', 'N/A')}
    Event Type: {alert.get('decoder', {}).get('name', 'N/A')}
    Process: {alert.get('data', {}).get('process', 'N/A')}
    User: {alert.get('data', {}).get('srcuser', 'N/A')}
    """

def _create_alert_context(alert: Dict[str, Any], context_data: Dict[str, Any]) -> str:
    """創建警報上下文摘要"""
    similar_count = len(context_data.get('similar_alerts', []))
    return f"""
    Similar Alerts Found: {similar_count}
    Time Window Analyzed: 30 minutes
    Related Hosts: {_extract_related_hosts(context_data)}
    Related IPs: {_extract_related_ips(context_data)}
    """

def _extract_related_hosts(context_data: Dict[str, Any]) -> str:
    """從上下文中提取相關主機"""
    hosts = set()
    for alerts in context_data.values():
        if isinstance(alerts, list):
            for alert in alerts:
                if isinstance(alert, dict) and 'agent' in alert:
                    hosts.add(alert['agent'].get('name', ''))
    return ', '.join(filter(None, hosts)) or 'None'

def _extract_related_ips(context_data: Dict[str, Any]) -> str:
    """從上下文中提取相關 IP"""
    ips = set()
    for alerts in context_data.values():
        if isinstance(alerts, list):
            for alert in alerts:
                if isinstance(alert, dict) and 'data' in alert:
                    ips.add(alert['data'].get('srcip', ''))
                    ips.add(alert['data'].get('dstip', ''))
    return ', '.join(filter(None, ips)) or 'None'

def _parse_graph_queries(response) -> List[Dict[str, Any]]:
    """解析 LLM 生成的圖形查詢"""
    import json
    
    try:
        content = response.content if hasattr(response, 'content') else str(response)
        
        # 尋找 JSON 陣列
        start_idx = content.find('[')
        end_idx = content.rfind(']') + 1
        
        if start_idx != -1 and end_idx > start_idx:
            json_str = content[start_idx:end_idx]
            queries = json.loads(json_str)
            
            # 驗證查詢格式
            validated = []
            for query in queries:
                if isinstance(query, dict) and 'cypher_template' in query:
                    validated.append(query)
            
            return validated
            
    except Exception as e:
        logger.warning(f"Failed to parse graph queries: {e}")
    
    return []

def _get_default_graph_queries(alert: Dict[str, Any]) -> List[Dict[str, Any]]:
    """提供預設的圖形查詢模板"""
    queries = []
    
    # 基於警報類型生成預設查詢
    if alert.get('data', {}).get('srcip'):
        queries.append({
            "name": "ip_activity_pattern",
            "cypher_template": """
            MATCH (ip:IP {address: $ip})-[r:TRIGGERED|CONNECTED_TO*1..3]-(related)
            WHERE related:Alert OR related:Host
            RETURN ip, r, related
            LIMIT 20
            """,
            "parameters": {"ip": alert['data']['srcip']},
            "purpose": "Analyze IP address activity patterns"
        })
    
    if alert.get('agent', {}).get('name'):
        queries.append({
            "name": "host_attack_timeline",
            "cypher_template": """
            MATCH (h:Host {name: $hostname})-[r:TRIGGERED]-(a:Alert)
            WHERE a.timestamp > datetime() - duration('PT30M')
            RETURN h, r, a
            ORDER BY a.timestamp DESC
            LIMIT 50
            """,
            "parameters": {"hostname": alert['agent']['name']},
            "purpose": "Get recent alerts from the same host"
        })
    
    return queries