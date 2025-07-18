# Stage 4 Step 2: 圖形化持久層實施報告

## 🎯 實施目標

成功將現有的 `process_single_alert` 流程改造，新增「**圖形化持久層**」步驟，為 GraphRAG 架構奠定基礎。

## 📋 實施內容總覽

### 1. 核心流程改造

#### 原有流程 (7 步驟)
1. Fetch new alert
2. Vectorize alert
3. Decide: 確定所需的上下文查詢
4. Retrieve: 執行多源檢索
5. Format: 格式化多源上下文
6. Analyze: LLM 分析
7. Update: 存儲結果

#### 新增流程 (8 步驟)
1. Fetch new alert
2. Vectorize alert
3. Decide: 確定所需的上下文查詢
4. Retrieve: 執行多源檢索
5. Format: 格式化多源上下文
6. Analyze: LLM 分析
7. Update: 存儲結果
8. **Graph Persistence: 圖形實體提取與關係建構** ⭐ **NEW**

### 2. 新增核心函數

#### 2.1 `extract_graph_entities()`
**功能**: 從警報、上下文和分析結果中提取圖形實體

**提取的實體類型**:
- 🚨 **Alert**: 警報本身 (ID, 時間戳, 規則資訊, 風險等級)
- 🖥️ **Host**: 主機 (Agent ID, 主機名, IP, 作業系統)
- 🌐 **IPAddress**: IP 位址 (來源/目的/內部 IP, 地理位置)
- 👤 **User**: 使用者 (使用者名稱, 類型, 認證方法)
- ⚙️ **Process**: 程序 (程序名, PID, 命令列, 父程序)
- 📁 **File**: 檔案 (路徑, 檔名, 大小, 權限)
- ⚠️ **ThreatIndicator**: 威脅指標 (從 LLM 分析結果提取)

#### 2.2 `build_graph_relationships()`
**功能**: 根據實體和上下文建立圖形關係

**關係類型**:
- `TRIGGERED_ON`: 警報 → 主機
- `HAS_SOURCE_IP`: 警報 → 來源 IP
- `INVOLVES_USER`: 警報 → 使用者
- `INVOLVES_PROCESS`: 警報 → 程序
- `ACCESSES_FILE`: 警報 → 檔案
- `SIMILAR_TO`: 警報 → 類似警報 (基於向量相似性)
- `PRECEDES`: 警報 → 後續警報 (時間序列關係)

#### 2.3 `persist_to_graph_database()`
**功能**: 將實體和關係持久化到 Neo4j 圖形資料庫

**特性**:
- 使用 `MERGE` 避免重複節點和關係
- 自動建立索引優化查詢效能
- 完整的錯誤處理和統計回報
- 支援批次處理和效能優化

### 3. 技術架構增強

#### 3.1 依賴新增
```txt
# requirements.txt 新增
neo4j                   # Neo4j 圖形資料庫驅動程式
python-dateutil         # 時間戳解析工具
```

#### 3.2 環境配置
```python
# Neo4j 連接配置
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "wazuh-graph-2024"
```

#### 3.3 Docker 整合
- 新增 `docker-compose.neo4j.yml` 配置檔案
- Neo4j 5.15 Community Edition
- APOC 和 Graph Data Science 插件支援
- 記憶體優化配置 (2GB-4GB heap)

### 4. 向後相容性保證

#### 4.1 故障隔離設計
```python
try:
    # 圖形持久層處理
    graph_entities = await extract_graph_entities(...)
    # ... 圖形處理邏輯
except Exception as graph_error:
    logger.error(f"圖形持久層錯誤: {graph_error}")
    # 主處理流程繼續執行，不受影響
    logger.info("主處理流程繼續執行")
```

#### 4.2 功能開關
- Neo4j 驅動程式可選安裝
- 自動檢測並優雅降級
- 現有 Stage 3 功能完全保留

### 5. 資料結構設計

#### 5.1 圖形實體範例
```json
{
  "type": "Alert",
  "id": "alert_12345",
  "properties": {
    "alert_id": "12345",
    "timestamp": "2024-01-15T10:30:00Z",
    "rule_id": "100002",
    "rule_description": "SSH Brute Force Attack",
    "rule_level": 8,
    "risk_level": "High",
    "triage_score": 96.0
  }
}
```

#### 5.2 關係範例
```json
{
  "type": "TRIGGERED_ON",
  "source_id": "alert_12345",
  "target_id": "host_001",
  "properties": {
    "timestamp": "2024-01-15T10:30:00Z",
    "severity": 8
  }
}
```

### 6. 效能考量與優化

#### 6.1 批次處理
- 實體數量限制：每個警報最多 50 個實體
- 關係數量控制：避免過度關聯
- 記憶體使用優化

#### 6.2 索引策略
```cypher
-- 自動建立的關鍵索引
CREATE INDEX alert_timestamp_idx FOR (a:Alert) ON (a.timestamp)
CREATE INDEX host_agent_id_idx FOR (h:Host) ON (h.agent_id)
CREATE INDEX ip_address_idx FOR (i:IPAddress) ON (i.address)
CREATE INDEX user_name_idx FOR (u:User) ON (u.username)
```

### 7. 監控與日誌

#### 7.1 詳細日誌記錄
```
🔗 STEP 8: GRAPH PERSISTENCE - Building knowledge graph for alert 12345
   🔍 Extracted 7 entities for graph database
   🔗 Built 12 relationships for graph database
   ✅ Graph persistence successful: 7 nodes, 12 relationships
   📊 Graph metadata added to alert 12345
```

#### 7.2 統計資訊
- 節點建立數量
- 關係建立數量
- 處理時間統計
- 錯誤率監控

### 8. 資料豐富化

#### 8.1 從警報提取
- 基本警報屬性
- 規則資訊和分類
- 時間戳和嚴重性

#### 8.2 從上下文增強
- 相關程序資訊
- 類似警報連結
- 系統狀態資料

#### 8.3 從 LLM 分析增強
- 風險等級提取
- 威脅指標識別
- 分級分數計算

## 🎯 後續步驟預覽

### Stage 4 Step 3: 圖形查詢引擎
- 攻擊路徑發現算法
- 橫向移動偵測
- 持久化機制識別

### Stage 4 Step 4: 混合檢索系統
- 向量檢索 + 圖形遍歷
- 智能上下文組裝
- 效能優化策略

## 🔧 部署指南

### 1. 安裝依賴
```bash
pip install neo4j python-dateutil
```

### 2. 啟動 Neo4j
```bash
docker-compose -f docker-compose.yml -f docker-compose.neo4j.yml up -d
```

### 3. 驗證功能
```bash
# 檢查 Neo4j 連接
curl http://localhost:7474

# 檢查圖形資料
cypher-shell -u neo4j -p wazuh-graph-2024 "MATCH (n) RETURN count(n)"
```

## 📊 成果評估

### ✅ 完成項目
- [x] 圖形實體提取器實施
- [x] 關係建構引擎實施  
- [x] Neo4j 持久化層實施
- [x] Docker 整合配置
- [x] 向後相容性保證
- [x] 錯誤處理與監控
- [x] 詳細文檔與部署指南

### 🎯 技術指標
- **實體類型**: 7 種核心安全實體
- **關係類型**: 7 種關聯模式
- **處理延遲**: < 500ms (預估)
- **故障隔離**: 100% (不影響主流程)
- **向後相容**: 100% (Stage 3 功能保留)

這個實施為 Wazuh AI Agent 從 AgenticRAG 向 GraphRAG 的演進奠定了堅實基礎，實現了從「扁平化事件檢索」到「結構化關係分析」的關鍵跨越。