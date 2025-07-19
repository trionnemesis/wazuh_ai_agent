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