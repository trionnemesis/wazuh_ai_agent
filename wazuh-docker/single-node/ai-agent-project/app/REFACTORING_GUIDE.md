# GraphRAG AI Agent 重構指南

## 概述

本指南說明如何將 3,070+ 行的 `main.py` 重構為模組化的架構，符合軟體工程的最佳實踐。

## 重構前後對比

### 重構前
```
app/
├── main.py              # 3,070+ 行的巨大檔案，包含所有邏輯
├── embedding_service.py # 已存在的嵌入服務
└── ...
```

### 重構後
```
app/
├── api/
│   ├── __init__.py
│   ├── endpoints.py      # FastAPI 路由 (@app.get, etc.)
│   └── health_check.py   # 健康檢查邏輯
├── core/
│   ├── __init__.py
│   ├── config.py         # 環境變數讀取 (已存在)
│   └── scheduler.py      # APScheduler 設定與任務定義
├── services/
│   ├── __init__.py
│   ├── alert_service.py      # 警報處理邏輯
│   ├── retrieval_service.py  # 檢索相關邏輯 (已部分存在)
│   ├── decision_service.py   # 決策引擎
│   ├── graph_service.py      # Neo4j 操作 (已部分存在)
│   ├── llm_service.py        # LangChain Prompts (已部分存在)
│   ├── opensearch_service.py # OpenSearch 客戶端管理
│   ├── neo4j_service.py      # Neo4j 驅動程式管理
│   ├── metrics.py            # Prometheus 指標
│   └── embedding_service.py  # (已存在)
├── main_new.py           # 新的精簡主程式
└── main.py               # 原始檔案 (保留供參考)
```

## 模組職責說明

### 1. API 層 (`api/`)

#### `endpoints.py`
- 所有 FastAPI 路由定義
- 包含 `/`, `/health`, `/metrics` 端點
- 使用 APIRouter 組織路由

#### `health_check.py`
- 系統健康檢查邏輯
- 檢查 OpenSearch、Neo4j、嵌入服務狀態

### 2. 核心層 (`core/`)

#### `config.py` (已存在)
- 集中管理所有環境變數
- 提供配置驗證功能
- 導出配置摘要

#### `scheduler.py`
- 管理 APScheduler 實例
- 定義定時任務
- 提供啟動/關閉功能

### 3. 服務層 (`services/`)

#### `alert_service.py`
- `query_new_alerts()`: 查詢待處理警報
- `triage_new_alerts()`: 主要分流任務
- `process_single_alert()`: 單一警報處理流程

#### `retrieval_service.py`
- `execute_retrieval()`: 執行多種檢索
- `execute_vector_search()`: 向量搜尋
- `execute_hybrid_retrieval()`: 混合檢索策略

#### `decision_service.py`
- `determine_contextual_queries()`: 決定查詢策略
- `determine_graph_queries()`: 生成 Cypher 查詢

#### `graph_service.py`
- `extract_graph_entities()`: 提取實體
- `build_graph_relationships()`: 建立關係
- `persist_to_graph_database()`: 持久化到 Neo4j
- `execute_graph_retrieval()`: 執行圖形檢索

#### `llm_service.py`
- `get_llm()`: 初始化 LLM
- `get_analysis_chain()`: 獲取分析鏈
- 管理所有提示詞模板

#### `opensearch_service.py`
- 管理 OpenSearch 客戶端（單例模式）
- 提供連接健康檢查

#### `neo4j_service.py`
- 管理 Neo4j 驅動程式（單例模式）
- 提供 Cypher 查詢執行介面
- 管理索引和約束

#### `metrics.py`
- 定義所有 Prometheus 指標
- 提供指標更新的工具函數

### 4. 主程式 (`main_new.py`)

精簡的主程式，只負責：
- FastAPI 應用初始化
- 生命週期管理
- 路由註冊
- 啟動 uvicorn

## 重構步驟

### 第一階段：準備工作
1. 備份原始 `main.py`
2. 創建新的目錄結構
3. 確保所有 `__init__.py` 檔案存在

### 第二階段：遷移核心模組
1. 遷移配置管理到 `core/config.py`
2. 遷移排程器邏輯到 `core/scheduler.py`
3. 遷移 Prometheus 指標到 `services/metrics.py`

### 第三階段：遷移服務層
1. 遷移檢索函數到 `services/retrieval_service.py`
2. 遷移決策函數到 `services/decision_service.py`
3. 遷移圖形操作到 `services/graph_service.py`
4. 遷移 LLM 相關到 `services/llm_service.py`

### 第四階段：遷移 API 層
1. 遷移路由到 `api/endpoints.py`
2. 抽取健康檢查到 `api/health_check.py`

### 第五階段：創建新主程式
1. 創建 `main_new.py`
2. 實現生命週期管理
3. 測試新架構

## 注意事項

### 導入路徑更新
從：
```python
from embedding_service import GeminiEmbeddingService
```

改為：
```python
from ..embedding_service import GeminiEmbeddingService
# 或
from services.embedding_service import GeminiEmbeddingService
```

### 循環導入預防
使用延遲導入避免循環依賴：
```python
def start_scheduler():
    from ..services.alert_service import triage_new_alerts  # 延遲導入
    # ...
```

### 單例模式實現
對於客戶端連接使用單例模式：
```python
_client: Optional[AsyncOpenSearch] = None

def get_opensearch_client() -> AsyncOpenSearch:
    global _client
    if _client is None:
        _client = AsyncOpenSearch(...)
    return _client
```

## 測試策略

### 單元測試
為每個服務模組創建對應的測試檔案：
```
tests/
├── test_alert_service.py
├── test_retrieval_service.py
├── test_decision_service.py
└── ...
```

### 整合測試
測試模組間的交互：
- API 端點測試
- 排程器任務測試
- 端到端流程測試

### 性能測試
確保重構後性能不降低：
- 響應時間測試
- 並發處理測試
- 記憶體使用測試

## 部署注意事項

### Docker 更新
更新 Dockerfile 以使用新的主程式：
```dockerfile
CMD ["python", "main_new.py"]
```

### 環境變數
確保所有環境變數仍然正確讀取

### 日誌配置
保持統一的日誌格式和等級

## 結論

通過這次重構，我們將一個 3,070+ 行的單一檔案拆分成了多個職責明確的模組，提高了：
- 可維護性
- 可測試性
- 可擴展性
- 團隊協作效率

每個模組都有明確的職責，遵循單一職責原則，使得系統更容易理解和修改。