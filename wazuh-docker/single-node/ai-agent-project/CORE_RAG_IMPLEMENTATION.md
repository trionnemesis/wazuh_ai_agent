# 核心 RAG 實現 - 相似警報檢索與關聯分析

## 🎯 概述

本階段實現了**agenticRAG**的核心「R」(Retrieval) 能力，讓 AI Agent 能在分析新警報前，先從歷史數據中檢索相關線索，提供更豐富的上下文給 LLM，產生更具深度的分析報告。

## 🔧 核心實現

### 1. 檢索模組 (AlertRetrievalModule)

新增專門的檢索模組類別，負責：

```python
class AlertRetrievalModule:
    async def retrieve_similar_alerts(self, query_vector: List[float], k: int = 5)
    def format_historical_context(self, similar_alerts: List[Dict[str, Any]])
```

**關鍵特性：**
- ✅ 執行 OpenSearch k-NN 搜尋
- ✅ 只檢索已有AI分析的歷史警報 (避免循環參考)
- ✅ 返回相似度分數和完整警報元數據
- ✅ 詳細的日誌記錄供除錯使用

### 2. 優化的 Prompt Template

```python
prompt_template = ChatPromptTemplate.from_template(
    """You are a senior security analyst with access to historical alert analysis...
    
    **Relevant Historical Alerts:**
    {historical_context}
    
    **Current Wazuh Alert to Analyze:**
    {alert_summary}
    
    **Your Enhanced Analysis Task:**
    1. **Event Summary**: Briefly describe what happened in this alert.
    2. **Historical Pattern Analysis**: Based on the historical alerts above...
    3. **Risk Assessment**: Assess considering both current alert and historical context.
    4. **Contextual Insights**: Provide insights based on historical data...
    5. **Actionable Recommendation**: Provide specific recommendation based on analysis.
    """
)
```

**增強功能：**
- ✅ 新增 `{historical_context}` 變數
- ✅ 要求LLM進行歷史模式分析
- ✅ 基於歷史數據提供洞察
- ✅ 更具體的分析任務結構

### 3. 整合主流程

**優化後的處理流程：**

```python
async def process_single_alert(alert: Dict[str, Any]) -> None:
    # 步驟 1: 向量化警報
    alert_vector = await vectorize_alert(alert_source)
    
    # 步驟 2: 使用檢索模組搜尋相似警報
    similar_alerts = await retrieval_module.retrieve_similar_alerts(alert_vector, k=5)
    
    # 步驟 3: 格式化歷史警報上下文
    historical_context = retrieval_module.format_historical_context(similar_alerts)
    
    # 步驟 4: AI 分析 (包含歷史上下文)
    analysis_result = await analyze_alert(alert_summary, historical_context, context)
    
    # 步驟 5: 更新警報
    await update_alert_with_analysis_and_vector(...)
```

## 🔍 檢索查詢詳細配置

**OpenSearch k-NN 查詢：**
```json
{
  "query": {
    "bool": {
      "must": [
        {
          "knn": {
            "alert_vector": {
              "vector": [查詢向量],
              "k": 5
            }
          }
        }
      ],
      "filter": [
        {"exists": {"field": "ai_analysis"}}
      ]
    }
  },
  "_source": {
    "includes": [
      "rule.description", "rule.level", "rule.id",
      "agent.name", "agent.ip", 
      "timestamp", "ai_analysis.triage_report",
      "location", "full_log"
    ]
  }
}
```

**關鍵配置說明：**
- `k=5`: 返回最相似的5筆歷史警報
- `filter`: 只檢索已分析的警報，避免循環依賴
- `_source.includes`: 只檢索必要欄位，優化效能

## 📊 歷史上下文格式化

**輸出格式：**
```
以下是相關的歷史警報分析參考：

【歷史警報 #1】(相似度: 0.847)
規則: Failed login attempt (等級: 5)
主機: web-server-01 (192.168.1.100)
時間: 2024-01-15T10:30:00Z
之前分析: This appears to be a brute force attack attempt targeting the SSH service...
---

【歷史警報 #2】(相似度: 0.798)
規則: Multiple failed login attempts (等級: 7)
主機: web-server-01 (192.168.1.100)
時間: 2024-01-15T09:45:00Z
之前分析: Escalating security incident - same IP attempting login failures...
---
```

## 🎯 驗收標準

### ✅ 1. k-NN 查詢執行確認

**透過日誌確認：**
```
INFO - ✅ 檢索模組找到 3 筆相似歷史警報
INFO -   相似警報 #1: 分數=0.8472, 規則=Failed login attempt
INFO -   相似警報 #2: 分數=0.7981, 規則=Multiple failed login
INFO -   相似警報 #3: 分數=0.7234, 規則=SSH brute force
```

### ✅ 2. 歷史上下文注入確認

**透過日誌確認：**
```
INFO - 📝 Step 3: 格式化歷史警報上下文
INFO - ✅ 格式化了 3 筆歷史警報上下文，總長度: 1247 字元
```

### ✅ 3. 報告品質提升驗證

**第一階段報告範例：**
```
Event Summary: Failed SSH login attempt detected.
Risk Assessment: Medium
Recommendation: Monitor for additional attempts.
```

**核心RAG階段報告範例：**
```
Event Summary: Failed SSH login attempt from IP 192.168.1.50.

Historical Pattern Analysis: This IP address has triggered 3 similar failed login alerts in the past 6 hours, indicating a potential brute force attack campaign.

Risk Assessment: High - Based on historical context showing escalating attack pattern.

Contextual Insights: Previous analysis indicated this is part of a coordinated attack. The same source has been attempting various usernames systematically.

Actionable Recommendation: Immediately block IP 192.168.1.50 and implement rate limiting on SSH service. Investigate if any login attempts were successful.
```

## 🚀 部署與測試

### 環境變數配置
```bash
# OpenSearch 配置
OPENSEARCH_URL=https://wazuh.indexer:9200
OPENSEARCH_USER=admin
OPENSEARCH_PASSWORD=SecretPassword

# LLM 配置
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_api_key

# Gemini Embedding
GEMINI_API_KEY=your_gemini_key
```

### 啟動服務
```bash
cd wazuh-docker/single-node/ai-agent-project
docker-compose up -d
```

### 監控日誌
```bash
docker-compose logs -f ai-agent
```

### 健康檢查
```bash
curl http://localhost:8000/health
```

**預期回應：**
```json
{
  "status": "healthy",
  "opensearch": "connected",
  "llm_provider": "anthropic", 
  "embedding_dimension": 768,
  "retrieval_module": "active"
}
```

## 🔬 檢索模組測試

可以使用 `test_retrieval_module.py` 腳本測試檢索功能：

```bash
python test_retrieval_module.py
```

## 📈 效能指標

**目標指標：**
- k-NN 搜尋回應時間: < 500ms
- 歷史上下文格式化: < 100ms
- 總體分析時間提升: < 20%
- 分析報告品質顯著提升

## 🔄 下一階段

1. **客製化檢索策略** - 根據警報類型調整檢索參數
2. **時間窗口過濾** - 只檢索特定時間範圍的歷史警報
3. **多維度檢索** - 結合規則類型、主機群組等維度
4. **動態k值調整** - 根據檢索品質動態調整返回數量

## 🏆 核心價值

通過實現檢索模組，AI Agent 現在能夠：

- 🧠 **學習歷史經驗** - 從過往分析中獲得洞察
- 🔍 **識別攻擊模式** - 檢測重複或升級的安全威脅  
- 📊 **提供量化背景** - 基於歷史數據給出具體統計
- 🎯 **精準風險評估** - 結合歷史趨勢評估當前風險
- 💡 **智慧建議** - 基於過往成功處理經驗提供建議

這標誌著從**單點分析**到**關聯分析**的重大躍進！