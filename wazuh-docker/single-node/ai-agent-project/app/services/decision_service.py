"""
決策服務模組
成為 Agentic AI 的 "大腦"，決定需要哪些資訊
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

from ..services.llm_service import get_llm
from ..core.config import NEO4J_URI
from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)

# === 規則引擎：常見場景的查詢策略 ===
RULE_BASED_STRATEGIES = {
    # SSH 相關規則
    "ssh_failed": {
        "patterns": ["ssh", "authentication failed", "invalid user", "failed password"],
        "queries": [
            {
                "type": "vector_similarity",
                "parameters": {"k": 10},
                "rationale": "Find similar SSH attack patterns"
            },
            {
                "type": "time_range",
                "parameters": {"field": "data.srcip", "minutes": 60},
                "rationale": "Track source IP activity in last hour"
            },
            {
                "type": "aggregation",
                "parameters": {"field": "data.srcuser", "metric": "count"},
                "rationale": "Analyze targeted user accounts"
            }
        ]
    },
    
    # 高 CPU 使用率
    "high_cpu": {
        "patterns": ["cpu usage", "high cpu", "cpu threshold", "performance"],
        "queries": [
            {
                "type": "time_range",
                "parameters": {"field": "agent.name", "minutes": 30},
                "rationale": "Check recent performance metrics"
            },
            {
                "type": "aggregation",
                "parameters": {"field": "data.process", "metric": "avg_cpu"},
                "rationale": "Identify resource-intensive processes"
            }
        ]
    },
    
    # 惡意軟體檢測
    "malware": {
        "patterns": ["malware", "virus", "trojan", "malicious", "threat detected"],
        "queries": [
            {
                "type": "vector_similarity",
                "parameters": {"k": 20},
                "rationale": "Find similar malware indicators"
            },
            {
                "type": "keyword",
                "parameters": {"field": "data.file_hash"},
                "rationale": "Track file hash across systems"
            },
            {
                "type": "time_range",
                "parameters": {"field": "agent.name", "minutes": 120},
                "rationale": "Analyze infection timeline"
            }
        ]
    },
    
    # 網路攻擊
    "network_attack": {
        "patterns": ["port scan", "brute force", "dos", "ddos", "flood"],
        "queries": [
            {
                "type": "vector_similarity",
                "parameters": {"k": 15},
                "rationale": "Identify attack patterns"
            },
            {
                "type": "aggregation",
                "parameters": {"field": "data.dstport", "metric": "count"},
                "rationale": "Analyze targeted ports"
            },
            {
                "type": "time_range",
                "parameters": {"field": "data.srcip", "minutes": 30},
                "rationale": "Track attacker activity"
            }
        ]
    },
    
    # 權限提升
    "privilege_escalation": {
        "patterns": ["privilege", "escalation", "sudo", "su ", "admin rights"],
        "queries": [
            {
                "type": "vector_similarity",
                "parameters": {"k": 10},
                "rationale": "Find similar privilege escalation attempts"
            },
            {
                "type": "time_range",
                "parameters": {"field": "data.srcuser", "minutes": 60},
                "rationale": "Track user activity timeline"
            },
            {
                "type": "keyword",
                "parameters": {"field": "data.command"},
                "rationale": "Analyze executed commands"
            }
        ]
    }
}

# === 決策相關的提示詞模板 ===

# Stage 3: Agentic 上下文查詢決策提示詞
contextual_query_prompt = ChatPromptTemplate.from_template(
    """As an AI security analyst, analyze this alert and determine what contextual information 
    would be most valuable for a comprehensive threat assessment.

    Alert Summary: {alert_summary}
    
    Base Queries Already Determined: {base_queries}

    Based on this alert, identify ADDITIONAL specific queries needed to gather contextual information.
    Consider temporal correlations, related processes, network patterns, and user behaviors.

    Your output should be a JSON array of query specifications. Each query should have:
    - type: One of ['vector_similarity', 'time_range', 'keyword', 'aggregation']
    - parameters: Specific parameters for that query type
    - rationale: Why this query is relevant

    Only suggest queries that are NOT already covered by the base queries.
    
    Generate the additional query specifications (empty array if none needed):
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
    
    採用「規則引擎為主，LLM增強為輔」的策略：
    1. 先使用規則引擎匹配常見場景（涵蓋80%情況）
    2. 對於複雜或未知場景，使用LLM生成額外查詢
    
    Args:
        alert: 原始警報資料
        
    Returns:
        List[Dict]: 查詢規格列表，每個包含查詢類型、參數和理由
    """
    try:
        # Step 1: 規則引擎 - 匹配常見場景
        base_queries = _apply_rule_based_strategies(alert)
        
        if base_queries:
            logger.info(f"📋 Rule Engine: Matched {len(base_queries)} queries for known scenario")
            
            # 對於已知場景，判斷是否需要 LLM 增強
            if _should_enhance_with_llm(alert):
                additional_queries = await _get_llm_enhanced_queries(alert, base_queries)
                base_queries.extend(additional_queries)
                logger.info(f"🤖 LLM Enhancement: Added {len(additional_queries)} additional queries")
        else:
            # Step 2: 未知場景 - 使用 LLM 生成策略
            logger.info("🤖 Unknown scenario detected, using LLM for query generation")
            base_queries = await _get_llm_generated_queries(alert)
        
        # Step 3: 添加通用查詢（始終執行）
        base_queries.extend(_get_universal_queries(alert))
        
        # 去重並返回
        return _deduplicate_queries(base_queries)
        
    except Exception as e:
        logger.error(f"Error in determine_contextual_queries: {str(e)}")
        # 降級到最基本的查詢策略
        return _get_fallback_queries(alert)

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

def _apply_rule_based_strategies(alert: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    應用規則引擎匹配常見場景
    
    Returns:
        List[Dict]: 匹配到的查詢策略
    """
    alert_text = _extract_alert_text(alert).lower()
    matched_queries = []
    
    for scenario, config in RULE_BASED_STRATEGIES.items():
        # 檢查是否匹配任何模式
        if any(pattern in alert_text for pattern in config["patterns"]):
            logger.debug(f"Matched scenario: {scenario}")
            # 深拷貝查詢並填充動態參數
            for query in config["queries"]:
                enriched_query = _enrich_query_with_alert_data(query.copy(), alert)
                matched_queries.append(enriched_query)
            break  # 只匹配第一個符合的場景
    
    return matched_queries

def _extract_alert_text(alert: Dict[str, Any]) -> str:
    """提取警報中的所有文本內容用於匹配"""
    parts = []
    
    # 規則描述
    rule_desc = alert.get('rule', {}).get('description')
    if rule_desc:
        parts.append(rule_desc)
    
    # 解碼器名稱
    decoder = alert.get('decoder', {}).get('name')
    if decoder:
        parts.append(decoder)
    
    # 數據字段
    data = alert.get('data', {})
    for field in ['command', 'process', 'action', 'status']:
        value = data.get(field)
        if value:
            parts.append(str(value))
    
    return ' '.join(parts)

def _enrich_query_with_alert_data(query: Dict[str, Any], alert: Dict[str, Any]) -> Dict[str, Any]:
    """使用警報數據豐富查詢參數"""
    params = query.get("parameters", {})
    
    # 動態替換參數值
    if "field" in params:
        field = params["field"]
        # 嘗試從警報中提取實際值
        if "." in field:
            parts = field.split(".")
            value = alert
            for part in parts:
                value = value.get(part, {})
                if not isinstance(value, dict):
                    params["value"] = value
                    break
    
    return query

def _should_enhance_with_llm(alert: Dict[str, Any]) -> bool:
    """判斷是否需要 LLM 增強"""
    # 高級別警報（7級以上）需要更深入的分析
    if alert.get('rule', {}).get('level', 0) >= 7:
        return True
    
    # 包含多個 IP 或複雜網路活動
    data = alert.get('data', {})
    if data.get('srcip') and data.get('dstip'):
        return True
    
    return False

async def _get_llm_enhanced_queries(alert: Dict[str, Any], base_queries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """使用 LLM 生成額外的查詢"""
    try:
        alert_summary = _create_alert_summary(alert)
        base_queries_summary = json.dumps(base_queries, indent=2)
        
        llm = get_llm()
        chain = contextual_query_prompt | llm
        
        response = await chain.ainvoke({
            "alert_summary": alert_summary,
            "base_queries": base_queries_summary
        })
        
        return _parse_llm_queries(response)
        
    except Exception as e:
        logger.warning(f"LLM enhancement failed: {e}")
        return []

async def _get_llm_generated_queries(alert: Dict[str, Any]) -> List[Dict[str, Any]]:
    """對於未知場景，使用 LLM 生成查詢"""
    try:
        # 使用原始的 LLM 提示詞，但設定超時和錯誤處理
        alert_summary = _create_alert_summary(alert)
        
        llm = get_llm()
        # 簡化的提示詞，減少 LLM 出錯機率
        simple_prompt = ChatPromptTemplate.from_template("""
        Analyze this security alert and suggest 3-5 queries to gather context.
        Alert: {alert_summary}
        
        Return a JSON array with query objects containing:
        - type: 'vector_similarity' or 'time_range' or 'keyword'
        - parameters: query parameters
        - rationale: why this query helps
        
        Example: [{"type": "vector_similarity", "parameters": {"k": 5}, "rationale": "Find similar alerts"}]
        """)
        
        chain = simple_prompt | llm
        response = await chain.ainvoke({"alert_summary": alert_summary})
        
        queries = _parse_llm_queries(response)
        if queries:
            return queries
            
    except Exception as e:
        logger.warning(f"LLM query generation failed: {e}")
    
    # 降級到基本策略
    return _get_default_queries(alert)

def _parse_llm_queries(response) -> List[Dict[str, Any]]:
    """安全地解析 LLM 回應"""
    try:
        content = response.content if hasattr(response, 'content') else str(response)
        
        # 嘗試多種解析方式
        # 1. 尋找 JSON 陣列
        start_idx = content.find('[')
        end_idx = content.rfind(']') + 1
        
        if start_idx != -1 and end_idx > start_idx:
            json_str = content[start_idx:end_idx]
            queries = json.loads(json_str)
            
            # 驗證查詢格式
            validated = []
            for query in queries:
                if isinstance(query, dict) and 'type' in query and 'parameters' in query:
                    # 確保有 rationale
                    if 'rationale' not in query:
                        query['rationale'] = 'LLM suggested query'
                    validated.append(query)
            
            return validated[:5]  # 最多返回 5 個查詢
            
    except Exception as e:
        logger.debug(f"Failed to parse LLM response: {e}")
    
    return []

def _get_universal_queries(alert: Dict[str, Any]) -> List[Dict[str, Any]]:
    """返回應該始終執行的通用查詢"""
    queries = []
    
    # 始終查找相似警報
    queries.append({
        "type": "vector_similarity",
        "parameters": {"k": 5},
        "rationale": "Always find similar historical alerts"
    })
    
    # 如果有主機名，查詢該主機最近活動
    if alert.get('agent', {}).get('name'):
        queries.append({
            "type": "time_range",
            "parameters": {
                "field": "agent.name",
                "value": alert['agent']['name'],
                "minutes": 15
            },
            "rationale": "Recent activity on the same host"
        })
    
    return queries

def _deduplicate_queries(queries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """去除重複的查詢"""
    seen = set()
    unique_queries = []
    
    for query in queries:
        # 創建查詢的唯一標識
        key = f"{query['type']}:{json.dumps(query.get('parameters', {}), sort_keys=True)}"
        if key not in seen:
            seen.add(key)
            unique_queries.append(query)
    
    return unique_queries

def _get_fallback_queries(alert: Dict[str, Any]) -> List[Dict[str, Any]]:
    """終極降級策略：返回最基本的查詢"""
    return [
        {
            "type": "vector_similarity",
            "parameters": {"k": 3},
            "rationale": "Basic similarity search"
        }
    ]

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
    Event Type: {alert.get('decoder', {}).get('name', 'N/A')}
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