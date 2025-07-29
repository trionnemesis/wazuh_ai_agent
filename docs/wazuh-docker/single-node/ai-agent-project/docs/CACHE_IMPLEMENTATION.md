# 智能快取 (Intelligent Caching) 實現文檔

## 概述

本文檔記錄了 Wazuh GraphRAG AI Agent 專案中智能快取機制的實現細節。快取系統旨在減少重複查詢，提升系統效能，並降低 API 調用成本。

## 實現架構

### 1. CacheManager 類 (`app/utils/cache_manager.py`)

專門為嵌入向量設計的快取管理器，使用 TTL (Time To Live) 策略。

**主要功能：**
- 單一查詢快取
- 批次查詢快取（支援部分命中）
- 快取統計追蹤
- 可配置的快取大小和過期時間

**核心方法：**
```python
class CacheManager:
    def __init__(self, maxsize: int = 1000, ttl: int = 3600, enabled: bool = True)
    def get(self, key: str) -> Optional[Any]
    def set(self, key: str, value: Any) -> None
    def get_batch(self, keys: List[str]) -> Dict[str, Any]
    def set_batch(self, items: Dict[str, Any]) -> None
    def get_stats(self) -> Dict[str, Any]
```

### 2. 快取裝飾器

#### embedding_cache
用於單一嵌入向量查詢的快取：
```python
@embedding_cache(cache_manager, prefix="embed")
async def embed_query(self, text: str) -> List[float]:
    # 實際的嵌入邏輯
```

#### batch_embedding_cache
用於批次嵌入向量查詢的快取，支援部分快取命中：
```python
@batch_embedding_cache(cache_manager, prefix="batch")
async def embed_documents(self, texts: List[str]) -> List[List[float]]:
    # 實際的批次嵌入邏輯
```

### 3. CacheService 類 (`app/services/cache_service.py`)

提供多層級快取策略的通用快取服務：
- LRU (Least Recently Used) 快取：用於高頻查詢
- TTL (Time To Live) 快取：用於時效性資料

## 整合實現

### 1. GeminiEmbeddingService 整合

**檔案：** `app/embedding_service.py`

- `embed_query()`: 使用 `@embedding_cache` 裝飾器
- `embed_documents()`: 使用 `@batch_embedding_cache` 裝飾器

### 2. Neo4j 查詢快取

**檔案：** `app/services/neo4j_service.py`

`execute_cypher_query()` 方法支援快取：
- 使用 LRU 快取策略
- 可通過 `use_cache` 參數控制

### 3. OpenSearch 查詢快取

**檔案：** `app/services/retrieval_service.py`

- `execute_vector_search()`: 向量相似度搜尋快取（TTL 5分鐘）
- `execute_keyword_time_search()`: 關鍵字時間範圍搜尋快取（TTL 5分鐘）

## 配置參數

### 環境變數

#### 嵌入向量快取配置
- `EMBEDDING_CACHE_SIZE`: 快取大小（預設: 1000）
- `EMBEDDING_CACHE_TTL`: TTL 秒數（預設: 3600）
- `EMBEDDING_CACHE_ENABLED`: 是否啟用（預設: true）

#### 通用快取配置
- `CACHE_ENABLED`: 是否啟用快取（預設: true）
- `CACHE_LRU_MAXSIZE`: LRU 快取大小（預設: 1000）
- `CACHE_TTL_MAXSIZE`: TTL 快取大小（預設: 500）
- `CACHE_TTL_SECONDS`: TTL 秒數（預設: 3600）

## 效能優勢

1. **減少 API 調用**
   - 相同的警報描述不需要重複呼叫 Gemini API
   - 節省 API 配額和成本

2. **提升響應速度**
   - 快取命中時可立即返回結果
   - 批次查詢支援部分快取，只計算未快取的項目

3. **降低資料庫負載**
   - Neo4j 和 OpenSearch 的常用查詢結果被快取
   - 減少資料庫連接和查詢執行時間

## 監控與統計

快取系統提供詳細的統計資訊：
- 命中率 (hit rate)
- 總請求數
- 命中/未命中次數
- 部分命中次數（批次查詢）
- 當前快取大小

可通過 API 端點查看快取統計：
```bash
GET /api/cache/stats
```

## 最佳實踐

1. **合理設置 TTL**
   - 向量嵌入：較長 TTL（1小時）
   - 查詢結果：較短 TTL（5-10分鐘）

2. **監控快取效能**
   - 定期檢查命中率
   - 根據使用模式調整快取大小

3. **快取鍵設計**
   - 使用內容的 MD5 雜湊作為鍵值
   - 包含有意義的前綴以區分不同類型的快取

## 未來優化方向

1. **分散式快取**
   - 考慮使用 Redis 支援多節點部署
   - 實現快取同步機制

2. **智能預載**
   - 根據使用模式預先載入常用資料
   - 實現預測性快取策略

3. **快取層級**
   - 實現多層快取架構
   - 記憶體快取 + 分散式快取組合