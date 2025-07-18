#!/usr/bin/env python3
"""
圖形持久層功能測試腳本
測試 Stage 4 Step 2 新增的圖形實體提取、關係建構和 Neo4j 持久化功能

執行方法:
python test_graph_persistence.py
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any

# 導入主模組中的圖形持久層函數
try:
    from main import (
        extract_graph_entities,
        build_graph_relationships,
        persist_to_graph_database,
        neo4j_driver
    )
    MAIN_MODULE_AVAILABLE = True
except ImportError as e:
    print(f"警告: 無法導入主模組函數: {e}")
    MAIN_MODULE_AVAILABLE = False

# 配置日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 測試資料：模擬 SSH 暴力破解攻擊警報
SAMPLE_ALERT = {
    '_id': 'test_alert_001',
    '_index': 'wazuh-alerts-test',
    '_source': {
        'timestamp': '2024-01-15T10:30:00.000Z',
        'rule': {
            'id': '5712',
            'description': 'SSH brute force trying to get access to the system.',
            'level': 10,
            'groups': ['syslog', 'sshd', 'authentication_failed', 'authentication_failures']
        },
        'agent': {
            'id': '001',
            'name': 'web-server-01',
            'ip': '10.0.1.100',
            'labels': {
                'os': 'Linux Ubuntu 20.04'
            }
        },
        'data': {
            'srcip': '203.0.113.45',
            'srcport': '45678',
            'dstip': '10.0.1.100',
            'dstport': '22',
            'user': 'admin',
            'srcuser': 'attacker',
            'protocol': 'tcp',
            'srcgeoip': {
                'country': 'CN',
                'city': 'Beijing'
            }
        }
    }
}

# 測試上下文資料
SAMPLE_CONTEXT_DATA = {
    'similar_alerts': [
        {
            '_id': 'similar_alert_001',
            '_score': 0.95,
            '_source': {
                'rule': {'description': 'SSH authentication failure'},
                'agent': {'name': 'web-server-01'}
            }
        },
        {
            '_id': 'similar_alert_002', 
            '_score': 0.87,
            '_source': {
                'rule': {'description': 'Multiple SSH login failures'},
                'agent': {'name': 'web-server-02'}
            }
        }
    ],
    'process_data': [
        {
            '_source': {
                'data': {
                    'process': {
                        'name': 'sshd',
                        'pid': '1234',
                        'cmdline': '/usr/sbin/sshd -D',
                        'ppid': '1'
                    }
                }
            }
        }
    ],
    'ssh_logs': [
        {
            '_source': {
                'data': {
                    'srcip': '203.0.113.45',
                    'user': 'admin'
                }
            }
        }
    ]
}

# 測試 LLM 分析結果
SAMPLE_ANALYSIS_RESULT = """
**Security Alert Analysis: SSH Brute Force Attack**

**Risk Level: HIGH**

This alert indicates a serious SSH brute force attack attempt against the web server. The attacker from IP 203.0.113.45 (Beijing, China) is attempting to gain unauthorized access to the system using multiple failed authentication attempts.

**Key Findings:**
1. High-frequency login attempts detected
2. Foreign IP address (203.0.113.45) targeting internal server
3. Multiple authentication failures for 'admin' user
4. Pattern consistent with automated attack tools

**Recommended Actions:**
1. Block source IP immediately
2. Review SSH configuration
3. Enable fail2ban protection
4. Monitor for lateral movement

**Impact Assessment: Critical** - Immediate action required to prevent potential system compromise.
"""

async def test_extract_graph_entities():
    """測試圖形實體提取功能"""
    print("\n" + "="*60)
    print("🔍 測試 1: 圖形實體提取 (extract_graph_entities)")
    print("="*60)
    
    if not MAIN_MODULE_AVAILABLE:
        print("❌ 主模組不可用，跳過測試")
        return None
    
    try:
        entities = await extract_graph_entities(
            SAMPLE_ALERT, 
            SAMPLE_CONTEXT_DATA, 
            SAMPLE_ANALYSIS_RESULT
        )
        
        print(f"✅ 成功提取 {len(entities)} 個實體")
        
        # 按類型統計實體
        entity_counts = {}
        for entity in entities:
            entity_type = entity['type']
            entity_counts[entity_type] = entity_counts.get(entity_type, 0) + 1
        
        print(f"📊 實體類型分布:")
        for entity_type, count in entity_counts.items():
            print(f"   - {entity_type}: {count}")
        
        # 顯示部分實體詳情
        print(f"\n📋 實體詳情範例:")
        for i, entity in enumerate(entities[:3]):  # 只顯示前3個
            print(f"   {i+1}. {entity['type']} ({entity['id']})")
            for key, value in list(entity['properties'].items())[:3]:
                print(f"      {key}: {value}")
        
        return entities
        
    except Exception as e:
        print(f"❌ 實體提取測試失敗: {str(e)}")
        logger.error(f"實體提取錯誤: {e}", exc_info=True)
        return None

async def test_build_graph_relationships(entities):
    """測試圖形關係建構功能"""
    print("\n" + "="*60)
    print("🔗 測試 2: 圖形關係建構 (build_graph_relationships)")
    print("="*60)
    
    if not MAIN_MODULE_AVAILABLE or not entities:
        print("❌ 依賴不可用，跳過測試")
        return None
    
    try:
        relationships = await build_graph_relationships(
            entities,
            SAMPLE_ALERT,
            SAMPLE_CONTEXT_DATA
        )
        
        print(f"✅ 成功建構 {len(relationships)} 個關係")
        
        # 按類型統計關係
        relationship_counts = {}
        for rel in relationships:
            rel_type = rel['type']
            relationship_counts[rel_type] = relationship_counts.get(rel_type, 0) + 1
        
        print(f"📊 關係類型分布:")
        for rel_type, count in relationship_counts.items():
            print(f"   - {rel_type}: {count}")
        
        # 顯示部分關係詳情
        print(f"\n📋 關係詳情範例:")
        for i, rel in enumerate(relationships[:3]):  # 只顯示前3個
            print(f"   {i+1}. {rel['source_id']} --[{rel['type']}]--> {rel['target_id']}")
            if rel.get('properties'):
                for key, value in list(rel['properties'].items())[:2]:
                    print(f"      {key}: {value}")
        
        return relationships
        
    except Exception as e:
        print(f"❌ 關係建構測試失敗: {str(e)}")
        logger.error(f"關係建構錯誤: {e}", exc_info=True)
        return None

async def test_persist_to_graph_database(entities, relationships):
    """測試 Neo4j 圖形資料庫持久化功能"""
    print("\n" + "="*60)
    print("💾 測試 3: 圖形資料庫持久化 (persist_to_graph_database)")
    print("="*60)
    
    if not MAIN_MODULE_AVAILABLE or not entities or not relationships:
        print("❌ 依賴不可用，跳過測試")
        return None
    
    try:
        result = await persist_to_graph_database(
            entities,
            relationships,
            SAMPLE_ALERT['_id']
        )
        
        if result['success']:
            print(f"✅ 圖形持久化成功")
            print(f"   📊 創建節點數: {result['nodes_created']}")
            print(f"   🔗 創建關係數: {result['relationships_created']}")
            print(f"   ⏰ 處理時間: {result['timestamp']}")
            
            if result.get('node_ids'):
                print(f"   🆔 節點 ID 範例: {result['node_ids'][:3]}...")
        else:
            print(f"❌ 圖形持久化失敗: {result.get('error', 'Unknown error')}")
        
        return result
        
    except Exception as e:
        print(f"❌ 圖形持久化測試失敗: {str(e)}")
        logger.error(f"圖形持久化錯誤: {e}", exc_info=True)
        return None

async def test_neo4j_connectivity():
    """測試 Neo4j 連接狀態"""
    print("\n" + "="*60)
    print("🔌 測試 0: Neo4j 連接狀態檢查")
    print("="*60)
    
    if not MAIN_MODULE_AVAILABLE:
        print("❌ 主模組不可用")
        return False
    
    if neo4j_driver is None:
        print("❌ Neo4j 驅動程式未初始化")
        print("   提示: 請確保 Neo4j 服務正在運行並且連接配置正確")
        return False
    
    try:
        async with neo4j_driver.session() as session:
            result = await session.run("CALL db.ping()")
            record = await result.single()
            
            if record:
                print("✅ Neo4j 連接成功")
                
                # 檢查資料庫狀態
                stats_result = await session.run("MATCH (n) RETURN count(n) as total_nodes")
                stats_record = await stats_result.single()
                total_nodes = stats_record['total_nodes'] if stats_record else 0
                
                print(f"   📊 資料庫統計: {total_nodes} 個節點")
                return True
            else:
                print("❌ Neo4j ping 失敗")
                return False
                
    except Exception as e:
        print(f"❌ Neo4j 連接測試失敗: {str(e)}")
        print(f"   提示: 請檢查 Neo4j 服務狀態和連接設定")
        return False

def print_test_summary(connectivity_ok, entities, relationships, persistence_result):
    """打印測試摘要"""
    print("\n" + "="*60)
    print("📊 測試結果摘要")
    print("="*60)
    
    total_tests = 4
    passed_tests = 0
    
    # 連接測試
    if connectivity_ok:
        print("✅ Neo4j 連接測試: 通過")
        passed_tests += 1
    else:
        print("❌ Neo4j 連接測試: 失敗")
    
    # 實體提取測試
    if entities:
        print(f"✅ 實體提取測試: 通過 ({len(entities)} 個實體)")
        passed_tests += 1
    else:
        print("❌ 實體提取測試: 失敗")
    
    # 關係建構測試
    if relationships:
        print(f"✅ 關係建構測試: 通過 ({len(relationships)} 個關係)")
        passed_tests += 1
    else:
        print("❌ 關係建構測試: 失敗")
    
    # 持久化測試
    if persistence_result and persistence_result.get('success'):
        print("✅ 圖形持久化測試: 通過")
        passed_tests += 1
    else:
        print("❌ 圖形持久化測試: 失敗")
    
    print(f"\n🎯 總計: {passed_tests}/{total_tests} 測試通過")
    
    if passed_tests == total_tests:
        print("🎉 所有測試通過！圖形持久層功能正常運作。")
    else:
        print("⚠️  部分測試失敗，請檢查配置和依賴。")
    
    return passed_tests == total_tests

async def main():
    """主測試函數"""
    print("🧪 圖形持久層功能測試開始")
    print(f"⏰ 測試時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 測試 0: Neo4j 連接
    connectivity_ok = await test_neo4j_connectivity()
    
    # 測試 1: 實體提取
    entities = await test_extract_graph_entities()
    
    # 測試 2: 關係建構
    relationships = await test_build_graph_relationships(entities)
    
    # 測試 3: 圖形持久化
    persistence_result = await test_persist_to_graph_database(entities, relationships)
    
    # 測試摘要
    all_passed = print_test_summary(connectivity_ok, entities, relationships, persistence_result)
    
    print(f"\n🏁 測試完成")
    return all_passed

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️  測試被用戶中斷")
        exit(130)
    except Exception as e:
        print(f"\n💥 測試過程中發生未預期錯誤: {str(e)}")
        logger.error(f"測試錯誤: {e}", exc_info=True)
        exit(1)