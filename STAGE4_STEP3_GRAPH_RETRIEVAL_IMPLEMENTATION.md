# Stage 4 Step 3: Graph-Native 檢索器實施報告

## 🎯 實施目標

成功開發 **Graph-Native 檢索器 (`execute_graph_retrieval`)**，取代現有的向量與關鍵字搜尋系統，實現從 AgenticRAG 到 GraphRAG 的核心轉變。

## 📋 實施內容總覽

### 1. 核心功能轉變

#### 從 AgenticRAG 到 GraphRAG
- **舊系統**: `execute_retrieval` → 向量相似性 + 關鍵字搜尋
- **新系統**: `execute_graph_retrieval` → Cypher 查詢 + 圖形遍歷
- **決策引擎角色轉變**: 決定檢索關鍵字 → 決定圖形查詢策略

#### Decision Engine 演進
- **舊版**: `determine_contextual_queries` → 生成 keyword/vector 查詢
- **新版**: `determine_graph_queries` → 生成 Cypher 查詢任務

### 2. 新增核心函數

#### 2.1 `execute_graph_retrieval(cypher_queries, alert)`
**功能**: GraphRAG 的核心檢索引擎

**輸入**:
- `cypher_queries`: 從決策引擎生成的 Cypher 查詢任務列表
- `alert`: 當前警報資料

**輸出**:
```python
{
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
```

**特性**:
- ✅ 自動降級機制（Neo4j 不可用時回退到傳統檢索）
- ✅ 查詢優先級排序
- ✅ 錯誤隔離和統計回報
- ✅ 按查詢類型自動分類結果

#### 2.2 `determine_graph_queries(alert)`
**功能**: Graph-Native 決策引擎

**智能場景檢測**:

1. **SSH 暴力破解場景**
   ```cypher
   // 攻擊來源全貌分析
   MATCH (alert:Alert {id: $alert_id})-[:HAS_SOURCE_IP]->(attacker:IPAddress)
   CALL {
       WITH attacker
       MATCH (related_alert:Alert)-[:HAS_SOURCE_IP]->(attacker)
       WHERE related_alert.timestamp > datetime() - duration({hours: 1})
       MATCH (related_alert)-[r]->(entity)
       WHERE type(r) <> 'MATCHED_RULE'
       RETURN related_alert, r, entity
   }
   RETURN *
   ```

2. **惡意軟體分析場景**
   ```cypher
   // 程序執行鏈分析
   MATCH (alert:Alert {id: $alert_id})-[:INVOLVES_PROCESS]->(process:Process)
   MATCH path = (process)-[:SPAWNED_BY*0..5]->(parent:Process)
   MATCH (parent)<-[:INVOLVES_PROCESS]-(related_alerts:Alert)
   WHERE related_alerts.timestamp > datetime() - duration({hours: 2})
   RETURN path, collect(related_alerts) as timeline
   ```

3. **網路攻擊場景**
   ```cypher
   // 網路攻擊拓撲分析
   MATCH (alert:Alert {id: $alert_id})-[:HAS_SOURCE_IP]->(attacker:IPAddress)
   MATCH (alert)-[:TRIGGERED_ON]->(target:Host)
   MATCH (attacker)-[:CONNECTED_TO*1..3]-(related_ips:IPAddress)
   MATCH (related_ips)<-[:HAS_SOURCE_IP]-(attack_alerts:Alert)
   WHERE attack_alerts.timestamp > datetime() - duration({hours: 6})
   RETURN attacker, target, related_ips, collect(attack_alerts) as attack_sequence
   ```

#### 2.3 `execute_hybrid_retrieval(alert)`
**功能**: 混合檢索系統

**智能策略**:
- 🔗 **優先使用圖形查詢**: 生成並執行 Cypher 查詢
- 📊 **智能補充**: 圖形結果不足時自動補充傳統檢索
- 🔄 **無縫整合**: 將兩種結果合併為統一格式

**閾值機制**: 圖形查詢結果 < 10 項時觸發傳統檢索補充

#### 2.4 `format_graph_context(context_data)`
**功能**: Graph-Native 上下文格式化

**10大分析維度**:
1. **攻擊路徑分析** - 重建完整攻擊鏈
2. **橫向移動檢測** - 多主機滲透分析
3. **時間序列關聯** - ±30分鐘關聯事件
4. **IP 信譽分析** - 地理位置和歷史活動
5. **使用者行為分析** - 7天基線對比
6. **程序執行鏈分析** - 父子程序關係
7. **檔案交互分析** - 檔案存取模式
8. **網路拓撲分析** - 6小時攻擊序列
9. **威脅全景分析** - 24小時高級威脅關聯
10. **傳統檢索補充** - 混合模式補充資料

#### 2.5 `format_hybrid_context(context_data)`
**功能**: 智能格式化路由器

**自動檢測邏輯**:
```python
graph_indicators = ['attack_paths', 'lateral_movement', 'temporal_sequences']
has_graph_data = any(context_data.get(indicator) for indicator in graph_indicators)

if has_graph_data:
    return format_graph_context(context_data)  # GraphRAG 格式化
else:
    return format_multi_source_context(context_data)  # 傳統格式化
```

### 3. LLM 提示詞演進

#### 3.1 GraphRAG 專用提示詞模板
**新增**: `graphrag_prompt_template`

**專業角色定義**:
> "You are a senior cyber security analyst with expertise in **graph-based threat hunting** and **advanced persistent threat (APT) analysis**."

**8大分析任務**:
1. **事件摘要與分類** - 基於圖形上下文威脅分類
2. **攻擊鏈重建** - 圖形關聯資料重建時間線
3. **橫向移動評估** - 滲透範圍和能力評估
4. **威脅行為者畫像** - 基於攻擊模式分析特徵
5. **風險等級評估** - 綜合圖形智能評級
6. **影響範圍分析** - 受影響資源確定
7. **緩解建議** - 基於圖形分析的精確建議
8. **持續威脅指標** - IOCs/IOAs 識別

#### 3.2 動態鏈選擇機制
**新增**: `get_analysis_chain(context_data)`

**智能路由**:
- 🔗 檢測到圖形資料 → 使用 `graphrag_prompt_template`
- 📊 檢測到傳統資料 → 使用 `traditional_prompt_template`

### 4. 處理流程整合

#### 4.1 `process_single_alert` 更新

**舊流程** (Stage 3):
```
Step 3: determine_contextual_queries → contextual_queries
Step 4: execute_retrieval(contextual_queries, alert_vector)
Step 5: format_multi_source_context(context_data)
Step 6: chain.ainvoke()
```

**新流程** (Stage 4):
```
Step 3: determine_graph_queries → graph_queries  
Step 4: execute_hybrid_retrieval(alert)
Step 5: format_hybrid_context(context_data)
Step 6: get_analysis_chain(context_data).ainvoke()
```

#### 4.2 元資料增強

**新增統計欄位**:
```python
context_metadata = {
    # Graph-native metrics
    "attack_paths_count": len(context_data.get('attack_paths', [])),
    "lateral_movement_count": len(context_data.get('lateral_movement', [])),
    "temporal_sequences_count": len(context_data.get('temporal_sequences', [])),
    "ip_reputation_count": len(context_data.get('ip_reputation', [])),
    "user_behavior_count": len(context_data.get('user_behavior', [])),
    # ... 更多圖形指標
    
    # Analysis metadata
    "stage": "Stage 4 - GraphRAG Analysis",
    "analysis_method": "Graph-Native Retrieval" or "Hybrid Retrieval"
}
```

### 5. 智能場景檢測

#### 5.1 SSH 暴力破解檢測
**觸發條件**: `'ssh' in rule_description and ('brute' in rule_description or 'failed' in rule_description)`

**生成查詢**:
- 🔑 攻擊來源全貌分析 (Critical)
- 🔄 橫向移動模式檢測 (High)

#### 5.2 惡意軟體檢測
**觸發條件**: `['malware', 'trojan', 'virus', 'suspicious', 'backdoor', 'rootkit']`

**生成查詢**:
- 🦠 程序執行鏈分析 (Critical)
- 📁 檔案系統影響分析 (High)

#### 5.3 網路攻擊檢測
**觸發條件**: `['web attack', 'sql injection', 'xss', 'command injection', 'http']`

**生成查詢**:
- 🌐 網路攻擊拓撲 (High)

#### 5.4 認證異常檢測
**觸發條件**: `['authentication', 'login', 'failed', 'privilege', 'escalation']`

**生成查詢**:
- 👤 使用者行為異常分析 (Medium)

#### 5.5 通用查詢
**總是執行**:
- ⏰ 時間序列關聯分析 (Medium)

**條件執行**:
- 🌍 IP 信譽分析 (檢測到外部IP時)
- ⚠️ 威脅全景分析 (警報級別 ≥ 8)

### 6. 錯誤處理與降級

#### 6.1 Neo4j 不可用時的優雅降級
```python
if not neo4j_driver:
    logger.warning("Neo4j driver not available - falling back to traditional retrieval")
    return await _fallback_to_traditional_retrieval(alert)
```

#### 6.2 Cypher 查詢失敗處理
```python
try:
    result = await session.run(cypher_query, parameters)
    records = await result.data()
except Exception as e:
    logger.error(f"Cypher query failed: {str(e)}")
    continue  # 繼續執行其他查詢
```

#### 6.3 分析鏈故障隔離
- 圖形持久化失敗不影響主流程
- 查詢失敗不影響其他查詢執行
- 格式化錯誤自動降級到傳統模式

### 7. 效能優化設計

#### 7.1 查詢優先級排序
```python
sorted_queries = sorted(cypher_queries, key=lambda x: {
    'critical': 0, 'high': 1, 'medium': 2, 'low': 3
}.get(x.get('priority', 'medium'), 2))
```

#### 7.2 結果限制和批次處理
- Cypher 查詢添加 `LIMIT` 子句
- 格式化結果限制顯示數量
- 避免記憶體過度使用

#### 7.3 連接池管理
- 使用 Neo4j AsyncDriver 連接池
- 自動會話管理和清理
- 連接失敗重試機制

### 8. 測試與驗證

#### 8.1 單元測試覆蓋
**新增**: `test_graphrag_retrieval.py`

**測試項目**:
- ✅ 圖形查詢生成測試
- ✅ 圖形檢索執行測試  
- ✅ 混合檢索系統測試
- ✅ 上下文格式化測試
- ✅ 分析鏈選擇測試

#### 8.2 場景測試資料
```python
test_scenarios = [
    "SSH brute force attack detected",      # SSH 暴力破解
    "Suspicious malware execution detected", # 惡意軟體檢測
    "SQL injection attack detected"         # 網路攻擊
]
```

#### 8.3 模擬環境支援
- 支援無 Neo4j 環境測試
- 模擬圖形查詢結果
- 自動降級邏輯驗證

### 9. 向後相容性

#### 9.1 Legacy 函數保留
- ✅ `determine_contextual_queries` - 保留供降級使用
- ✅ `execute_retrieval` - 混合檢索中調用
- ✅ `format_multi_source_context` - 傳統格式化保留

#### 9.2 資料格式相容
- 新增欄位向下相容
- 原有統計欄位繼續支援
- 分析報告格式向前相容

### 10. 部署與配置

#### 10.1 環境變數
```bash
# Neo4j 配置（可選）
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j  
NEO4J_PASSWORD=wazuh-graph-2024

# LLM 配置
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_key_here
```

#### 10.2 依賴安裝
```bash
# 已包含在 requirements.txt
neo4j>=5.15.0
python-dateutil>=2.8.0
```

#### 10.3 驗證部署
```bash
# 執行測試
python test_graphrag_retrieval.py

# 檢查功能
curl -X POST http://localhost:8000/triage
```

## 🎯 實施成果

### ✅ 完成項目
- [x] Graph-Native 檢索器實施 (`execute_graph_retrieval`)
- [x] Graph-Native 決策引擎 (`determine_graph_queries`)
- [x] 混合檢索系統 (`execute_hybrid_retrieval`)
- [x] 智能上下文格式化 (`format_graph_context`)
- [x] 動態 LLM 鏈選擇 (`get_analysis_chain`)
- [x] GraphRAG 專用提示詞模板
- [x] 處理流程完整整合
- [x] 錯誤處理與降級機制
- [x] 全面測試覆蓋
- [x] 向後相容性保證

### 📊 技術指標
- **支援場景**: 7 種智能威脅檢測場景
- **查詢類型**: 10 種圖形檢索類別
- **分析維度**: 10 大威脅分析維度
- **降級策略**: 3 層故障隔離機制
- **效能優化**: 4 項效能優化策略
- **測試覆蓋**: 5 項核心功能測試

### 🔗 GraphRAG 核心優勢

#### 1. **結構化威脅理解**
- 從扁平化事件檢索 → 結構化關係分析
- 攻擊路徑重建和橫向移動檢測
- 威脅行為者畫像和 IOC 追蹤

#### 2. **智能上下文關聯**
- 圖形遍歷發現隱藏關聯
- 時間序列和空間關係分析
- 多維度威脅情報整合

#### 3. **精確威脅評估**
- 基於圖形結構的風險計算
- 影響範圍和擴散路徑分析
- 精準緩解建議生成

#### 4. **可擴展架構設計**
- 模組化圖形查詢引擎
- 開放式場景檢測框架
- 靈活的混合檢索策略

## 🚀 Stage 4 Step 4 預覽

下一步將實施：
- **高級圖形演算法**: 攻擊路徑發現、社群檢測
- **實時威脅追蹤**: 持續監控和動態更新
- **智能預測分析**: 基於圖形模式的威脅預測
- **可視化儀表板**: 互動式威脅圖形展示

---

**這個實施標誌著 Wazuh AI Agent 從 AgenticRAG 成功演進到 GraphRAG，實現了從「相似事件檢索」到「結構化威脅分析」的關鍵跨越，為下一代網路安全分析奠定了堅實基礎。**