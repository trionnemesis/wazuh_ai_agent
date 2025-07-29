# Wazuh AgenticRAG 向量化系統

## 概述

本系統實現了 Wazuh 警報的語意向量化與儲存，為後續的 RAG (Retrieval-Augmented Generation) 功能奠定基礎。通過 Google Gemini Embedding API，系統能夠將警報內容轉換為高維向量，並利用這些向量進行語意相似搜尋，從而提供更準確的警報分析和上下文推薦。

## 🏗️ 架構設計

### 核心組件

1. **embedding_service.py** - Gemini Embedding 服務封裝
2. **main.py** - 重構後的模組化主程序
3. **setup_index_template.py** - OpenSearch 索引範本設置工具
4. **verify_vectorization.py** - 向量化流程驗證工具

### 數據流程

```
新 Wazuh 警報 → 向量化 → 相似搜尋 → LLM 分析 → 儲存結果 + 向量
```

## 🚀 快速開始

### 1. 環境配置

```bash
# 必須設置的環境變數
export GOOGLE_API_KEY="your-gemini-api-key"
export OPENSEARCH_URL="https://wazuh.indexer:9200"
export OPENSEARCH_USER="admin"
export OPENSEARCH_PASSWORD="SecretPassword"

# 可選的配置
export EMBEDDING_MODEL="models/text-embedding-004"
export EMBEDDING_DIMENSION="768"  # 或其他 1-768 的值
export LLM_PROVIDER="anthropic"   # 或 "gemini"
```

### 2. 設置索引範本

```bash
# 在 app 目錄下執行
python setup_index_template.py
```

### 3. 啟動系統

```bash
# 啟動 AI Agent
python main.py
```

### 4. 驗證系統

```bash
# 驗證向量化流程
python verify_vectorization.py
```

## 📋 功能特性

### Embedding 服務

- **多維度支援**: 支援 Matryoshka 表示學習 (MRL)，可配置 1-768 維向量
- **錯誤重試**: 內建指數退避重試機制
- **文本預處理**: 自動清理和截斷長文本
- **專門的警報向量化**: `embed_alert_content()` 方法針對警報結構優化

### 向量搜尋

- **語意相似搜尋**: 使用 cosine 相似度尋找相關歷史警報
- **HNSW 索引**: 高性能的近似最近鄰搜尋
- **動態上下文構建**: 根據相似警報自動構建分析上下文

### 模組化設計

- **查詢模組**: `query_new_alerts()` - 檢索待處理警報
- **向量化模組**: `vectorize_alert()` - 警報內容向量化
- **搜尋模組**: `find_similar_alerts()` - 相似警報搜尋
- **分析模組**: `analyze_alert()` - LLM 警報分析
- **更新模組**: `update_alert_with_analysis()` - 結果儲存

## 📊 OpenSearch 索引結構

### 索引範本: wazuh-alerts-vector-template

```json
{
  "mappings": {
    "properties": {
      "alert_vector": {
        "type": "dense_vector",
        "dims": 768,
        "index": true,
        "similarity": "cosine",
        "index_options": {
          "type": "hnsw",
          "m": 16,
          "ef_construction": 512
        }
      },
      "ai_analysis": {
        "type": "object",
        "properties": {
          "triage_report": {"type": "text"},
          "provider": {"type": "keyword"},
          "timestamp": {"type": "date"},
          "risk_level": {"type": "keyword"},
          "vector_dimension": {"type": "integer"},
          "processing_time_ms": {"type": "integer"}
        }
      }
    }
  }
}
```

## 🔧 配置選項

### Embedding 配置

| 環境變數 | 預設值 | 說明 |
|---------|--------|------|
| GOOGLE_API_KEY | - | Gemini API 金鑰 (必須) |
| EMBEDDING_MODEL | models/text-embedding-004 | 使用的 embedding 模型 |
| EMBEDDING_DIMENSION | 768 | 向量維度 (1-768) |
| EMBEDDING_MAX_RETRIES | 3 | 最大重試次數 |
| EMBEDDING_RETRY_DELAY | 1.0 | 重試間隔 (秒) |

### LLM 配置

| 環境變數 | 預設值 | 說明 |
|---------|--------|------|
| LLM_PROVIDER | anthropic | LLM 提供者 |
| ANTHROPIC_API_KEY | - | Claude API 金鑰 |
| GEMINI_API_KEY | - | Gemini API 金鑰 |

## 🛠️ 使用工具

### setup_index_template.py

**功能**: 設置和管理 OpenSearch 索引範本

```bash
python setup_index_template.py
```

**特性**:
- 自動檢測現有範本
- 互動式更新確認
- 範本配置驗證
- 向量操作測試

### verify_vectorization.py

**功能**: 全面驗證向量化流程

```bash
python verify_vectorization.py
```

**檢查項目**:
- Embedding 服務連通性
- 索引範本正確性
- 已向量化警報統計
- 向量搜尋功能
- 待處理警報數量

## 📈 監控和調試

### 健康檢查端點

```bash
curl http://localhost:8000/health
```

**回應示例**:
```json
{
  "status": "healthy",
  "opensearch": "connected",
  "embedding_service": "working",
  "vector_dimension": 768,
  "llm_provider": "anthropic"
}
```

### 日誌級別

- **INFO**: 一般運行狀態
- **DEBUG**: 詳細的向量化過程
- **WARNING**: 非致命錯誤
- **ERROR**: 嚴重錯誤

## 🔍 查看結果

### 在 Wazuh Dashboard 中

1. 進入 **Discover** 介面
2. 選擇 `wazuh-alerts-*` 索引模式
3. 搜尋條件: `ai_analysis:*`
4. 查看欄位:
   - `alert_vector`: 768 維浮點數陣列
   - `ai_analysis.triage_report`: AI 分析報告
   - `ai_analysis.vector_dimension`: 向量維度
   - `ai_analysis.provider`: 使用的 LLM 提供者

### 使用 OpenSearch API

```bash
# 查詢已向量化的警報
curl -X GET "https://wazuh.indexer:9200/wazuh-alerts-*/_search" \
     -u admin:SecretPassword \
     -k \
     -H "Content-Type: application/json" \
     -d '{
       "query": {
         "exists": {"field": "alert_vector"}
       },
       "size": 10
     }'
```

## ⚠️ 注意事項

### API 限制

- **Gemini API**: 每分鐘請求限制，長文本截斷
- **文本長度**: 自動截斷至 8000 字符
- **批次處理**: 單次處理 10 個警報

### 性能考量

- **向量維度**: 較高維度提供更好精度但消耗更多資源
- **搜尋效率**: HNSW 索引在大數據集上表現優異
- **記憶體使用**: 768 維向量每個約 3KB

### 錯誤處理

- **重試機制**: 自動重試失敗的 API 調用
- **降級策略**: 向量搜尋失敗時使用預設上下文
- **容錯設計**: 單個警報失敗不影響批次處理

## 🚦 故障排除

### 常見問題

1. **Embedding 服務失敗**
   - 檢查 GOOGLE_API_KEY 是否正確
   - 確認網路連接和 API 配額

2. **向量搜尋無結果**
   - 確認索引範本正確應用
   - 檢查是否有已向量化的歷史資料

3. **OpenSearch 連線失敗**
   - 驗證 URL 和認證資訊
   - 檢查憑證設置

### 偵錯步驟

1. 執行健康檢查: `curl http://localhost:8000/health`
2. 運行驗證腳本: `python verify_vectorization.py`
3. 檢查應用日誌查看詳細錯誤資訊
4. 使用 setup_index_template.py 重新配置索引

## 🔮 後續發展

本向量化系統為 AgenticRAG 的基礎階段，後續可擴展：

- **檢索增強**: 實現複雜的檢索策略
- **多模態**: 支援更多資料類型
- **即時搜尋**: WebSocket 即時向量搜尋
- **分析儀表板**: 向量化統計和效能監控

## 📞 支援

如遇問題，請檢查：
1. 環境變數配置
2. API 金鑰有效性
3. OpenSearch 連通性
4. 系統日誌資訊