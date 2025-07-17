# AgenticRAG 第一階段：警報向量化與儲存

## 概述

本階段實現將 Wazuh 警報轉換為語意向量並儲存到 OpenSearch，為後續的語意檢索奠定基礎。

## 功能特性

### ✅ 已實現功能

1. **模組化程式架構**
   - 重構 `main.py`，分離查詢、向量化、分析、更新等功能
   - 獨立的 `embedding_service.py` 模組
   - 完整的錯誤處理和重試機制

2. **Gemini Embedding 整合**
   - 支援 Google Gemini `text-embedding-004` 模型
   - Matryoshka 向量維度支援 (1-768)
   - 異步處理和重試機制

3. **OpenSearch 向量支援**
   - 自動建立索引模板包含 `alert_vector` 欄位
   - KNN 向量搜尋支援 (HNSW 算法)
   - 餘弦相似度計算

4. **完整工作流程**
   - 查詢新警報 → 向量化 → 語意搜尋 → AI 分析 → 更新儲存
   - 健康檢查和系統驗證

## 部署步驟

### 1. 環境配置

```bash
# 複製環境變數範例
cp .env.example .env

# 編輯環境變數
nano .env
```

必要的環境變數：
```bash
# OpenSearch 連接
OPENSEARCH_URL=https://wazuh.indexer:9200
OPENSEARCH_USER=admin
OPENSEARCH_PASSWORD=SecretPassword

# AI 模型配置
LLM_PROVIDER=anthropic  # 或 gemini
GOOGLE_API_KEY=your_google_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Embedding 配置
EMBEDDING_DIMENSION=768
```

### 2. 安裝依賴

```bash
pip install -r requirements.txt
```

### 3. 設定索引模板

```bash
# 執行索引模板設定
python setup_index_template.py
```

### 4. 系統驗證

```bash
# 執行完整系統測試
python test_system.py
```

### 5. 啟動服務

```bash
# 啟動 AI Agent
uvicorn main:app --host 0.0.0.0 --port 8000
```

## 驗證方法

### 自動驗證
執行 `python test_system.py` 進行完整驗證，包括：
- OpenSearch 連接測試
- Embedding 服務測試  
- 索引模板檢查
- 向量操作測試
- KNN 搜尋測試
- 端到端工作流程測試

### 手動驗證

1. **檢查健康狀態**
```bash
curl http://localhost:8000/health
```

2. **檢查索引模板**
```bash
curl -X GET "wazuh.indexer:9200/_template/wazuh-alerts-ai-template" \
     -u admin:SecretPassword -k
```

3. **檢查警報向量欄位**
在 Wazuh Dashboard 的 "Discover" 介面中：
- 選擇 `wazuh-alerts-*` 索引模式
- 查找包含 `alert_vector` 欄位的文件
- 確認 `alert_vector` 為數字陣列格式

## 檔案結構

```
app/
├── main.py                    # 主要應用程式 (重構後)
├── embedding_service.py       # Embedding 服務模組
├── setup_index_template.py    # 索引模板設定腳本
├── test_system.py            # 系統驗證腳本
├── requirements.txt          # Python 依賴
├── .env.example             # 環境變數範例
└── PHASE1_DEPLOYMENT.md     # 本文檔
```

## 核心元件說明

### EmbeddingService
- **功能**: 負責與 Google Gemini API 通信，將文本轉換為向量
- **特性**: 支援重試機制、維度配置、連接測試
- **使用**: `await embedding_service.embed_query(text)`

### 模組化函式
- `query_new_alerts()`: 查詢未分析的新警報
- `vectorize_alert()`: 將警報轉換為向量
- `find_similar_alerts()`: 使用向量搜尋相似警報
- `analyze_alert()`: LLM 分析警報
- `update_alert_with_analysis_and_vector()`: 更新警報加入分析和向量

### 索引模板
- **模板名稱**: `wazuh-alerts-ai-template`
- **索引模式**: `wazuh-alerts-*`
- **向量欄位**: `alert_vector` (knn_vector, 768維)
- **分析欄位**: `ai_analysis.*`

## 驗收標準 ✅

1. **向量欄位可見性**: 在 Wazuh Dashboard 中可看到 `alert_vector` 欄位
2. **持續穩定運行**: 服務可持續處理新警報無錯誤
3. **模組化架構**: 代碼結構清晰，功能分離
4. **完整測試覆蓋**: 所有核心功能都有對應測試

## 故障排除

### 常見問題

1. **Gemini API 連接失敗**
   - 檢查 `GOOGLE_API_KEY` 是否正確設定
   - 確認 API 配額和限制

2. **OpenSearch 連接問題**
   - 檢查 URL、用戶名、密碼設定
   - 確認 SSL 憑證配置

3. **向量搜尋失敗**
   - 檢查索引模板是否正確建立
   - 確認 KNN plugin 已啟用

### 日誌檢查
```bash
# 檢查應用程式日誌
docker logs wazuh-ai-agent

# 檢查 OpenSearch 日誌
docker logs wazuh.indexer
```

## 下一階段預覽

第二階段將實現：
- 進階語意搜尋和檢索
- 警報分類和風險評估
- 歷史警報關聯分析
- 動態知識庫更新