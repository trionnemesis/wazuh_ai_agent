# AI Agent 專案 - Wazuh GraphRAG 智能分析模組

## 📋 模組概述

AI Agent 是 Wazuh GraphRAG 系統的核心智能分析模組，實現了四階段演進式的圖形檢索增強生成架構。本模組負責：

- 🔍 **威脅實體識別**：從 Wazuh 警報中提取安全實體
- 🕸️ **關係圖譜構建**：建立威脅實體間的關聯網路
- 🧠 **智能語境分析**：結合歷史數據與圖形關係生成深度分析
- 📊 **效能監控整合**：提供完整的 Prometheus 指標輸出

## 🏗️ 模組架構

```
ai-agent-project/
├── app/                      # 主要應用程式碼
│   ├── main_new.py          # 模組化主程式進入點
│   ├── api/                 # API 路由層
│   │   └── routes.py        # FastAPI 端點定義
│   ├── core/                # 核心業務邏輯
│   │   ├── graph_entity_extractor.py      # 實體提取
│   │   ├── graph_relationship_builder.py   # 關係建構
│   │   ├── graph_query_engine.py          # Cypher 查詢
│   │   └── graph_context_assembler.py     # 上下文組裝
│   ├── services/            # 服務層
│   │   ├── embedding_service.py    # 向量化服務
│   │   ├── graph_service.py        # Neo4j 圖形服務
│   │   ├── retrieval_service.py    # 檢索服務
│   │   └── analysis_service.py     # LLM 分析服務
│   ├── stages/              # 階段性模組
│   │   ├── stage1_vector_rag.py    # 基礎向量化
│   │   ├── stage2_basic_rag.py     # 核心 RAG
│   │   ├── stage3_agentic_rag.py   # 代理關聯
│   │   └── stage4_graph_rag.py     # 圖形分析
│   └── utils/               # 工具模組
│       ├── config.py        # 配置管理
│       ├── logger.py        # 日誌工具
│       └── metrics.py       # 指標收集
├── tests/                   # 測試套件
├── docs/                    # 詳細文件
├── Dockerfile              # 容器配置
└── requirements.txt        # Python 依賴

```

## 🚀 快速開始

### 環境需求

- Python 3.11+
- Docker 20.10+
- 記憶體：最少 1GB

### 本地開發

```bash
# 建立虛擬環境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安裝依賴
pip install -r requirements.txt

# 設定環境變數
cp .env.example .env
# 編輯 .env 設定必要的 API 金鑰

# 啟動開發伺服器
uvicorn app.main_new:app --reload --host 0.0.0.0 --port 8000
```

### Docker 部署

```bash
# 建構映像檔
docker build -t wazuh-ai-agent .

# 執行容器
docker run -d \
  --name ai-agent \
  --env-file .env \
  -p 8000:8000 \
  wazuh-ai-agent
```

## 🔧 配置說明

### 必要環境變數

```bash
# LLM 配置
GOOGLE_API_KEY=your_gemini_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
LLM_PROVIDER=anthropic  # 或 'gemini'

# Neo4j 配置
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# OpenSearch 配置
OPENSEARCH_URL=https://wazuh.indexer:9200
OPENSEARCH_USER=admin
OPENSEARCH_PASSWORD=your_password

# GraphRAG 配置
ENABLE_GRAPH_PERSISTENCE=true
GRAPH_BATCH_SIZE=100
GRAPH_MAX_ENTITIES_PER_ALERT=50
```

### 進階配置

在 `app/utils/config.py` 中可調整：

- **向量檢索參數**：`VECTOR_SEARCH_K`、`VECTOR_SIMILARITY_THRESHOLD`
- **圖形查詢參數**：`GRAPH_TRAVERSAL_DEPTH`、`GRAPH_RESULT_LIMIT`
- **LLM 參數**：`LLM_TEMPERATURE`、`LLM_MAX_TOKENS`

## 📡 API 端點

### 健康檢查
```
GET /health
```

### 效能指標
```
GET /metrics
```

### 手動觸發處理
```
POST /process-alerts
```

## 🧪 測試

### 執行單元測試
```bash
pytest tests/ -v
```

### 執行整合測試
```bash
python tests/test_graphrag_retrieval.py
python tests/test_graph_persistence.py
```

### 效能測試
```bash
python performance_test.py
```

## 📊 監控與除錯

### 日誌查看
```bash
# Docker 環境
docker logs -f ai-agent

# 本地開發
tail -f logs/ai_agent.log
```

### 常見問題排查

1. **Neo4j 連接失敗**
   - 確認 Neo4j 服務已啟動
   - 檢查網路連通性
   - 驗證認證資訊

2. **OpenSearch 憑證錯誤**
   - 確認 SSL 憑證路徑正確
   - 檢查 `OPENSEARCH_SSL_VERIFY` 設定

3. **LLM API 錯誤**
   - 驗證 API 金鑰有效性
   - 檢查 API 配額限制

## 🔗 相關文件

- [主要專案說明](../../../README.md)
- [技術白皮書](../../../MERGED_DOCUMENTATION.md)
- [模組化架構指南](app/REFACTORING_GUIDE.md)
- [監控設置指南](docs/MONITORING_SETUP.md)

## 📝 版本資訊

- **當前版本**: 5.1.0 (模組化架構)
- **最後更新**: 2024年12月
- **Python 版本**: 3.11+
- **主要依賴**: FastAPI 0.100+, LangChain 0.0.300+, Neo4j 5.11+