# 向量欄位錯誤解決方案

## 錯誤訊息
```
ERROR - Vector search failed: RequestError(400, '{"error":... "reason":"failed to create query: Field 'alert_vector' is not knn_vector type."...}')
```

## 問題分析

### 錯誤含義
這個錯誤表示 OpenSearch 資料庫中的 `alert_vector` 欄位不是正確的向量類型。當 AI Agent 嘗試執行向量相似度搜尋時，OpenSearch 無法將該欄位識別為可進行 k-NN（k-nearest neighbors）搜尋的向量欄位。

### 根本原因
1. **索引模板未套用**：雖然已定義了正確的索引模板（`wazuh-alerts-vector-template.json`），但該模板可能尚未套用到 OpenSearch
2. **既有索引問題**：現有的 `wazuh-alerts-*` 索引可能在套用模板之前就已建立，因此沒有正確的向量欄位映射
3. **欄位類型不匹配**：`alert_vector` 欄位可能被建立為普通的數值陣列，而非 `dense_vector` 類型

## 解決方案

### 方案 1：使用快速修正腳本（推薦）

我已建立兩個修正腳本：

1. **`quick_fix_vector.py`** - 自動化快速修正腳本
2. **`fix_vector_field.py`** - 互動式詳細修正腳本

### 方案 2：手動修正步驟

#### 步驟 1：套用索引模板
```bash
# 在容器內執行
curl -X PUT "https://wazuh.indexer:9200/_index_template/wazuh-alerts-vector-template" \
  -H "Content-Type: application/json" \
  -u admin:SecretPassword \
  -k \
  -d @wazuh-alerts-vector-template.json
```

#### 步驟 2：重新索引現有資料
```bash
# 建立新索引（會自動套用模板）
curl -X PUT "https://wazuh.indexer:9200/wazuh-alerts-4.x-2024.01.01-temp" \
  -u admin:SecretPassword \
  -k

# 重新索引資料
curl -X POST "https://wazuh.indexer:9200/_reindex" \
  -H "Content-Type: application/json" \
  -u admin:SecretPassword \
  -k \
  -d '{
    "source": {"index": "wazuh-alerts-4.x-2024.01.01"},
    "dest": {"index": "wazuh-alerts-4.x-2024.01.01-temp"}
  }'

# 刪除舊索引並重新命名
curl -X DELETE "https://wazuh.indexer:9200/wazuh-alerts-4.x-2024.01.01" \
  -u admin:SecretPassword \
  -k

curl -X POST "https://wazuh.indexer:9200/_aliases" \
  -H "Content-Type: application/json" \
  -u admin:SecretPassword \
  -k \
  -d '{
    "actions": [
      {"add": {"index": "wazuh-alerts-4.x-2024.01.01-temp", "alias": "wazuh-alerts-4.x-2024.01.01"}}
    ]
  }'
```

### 方案 3：Docker Compose 整合

在 `docker-compose.yml` 中加入初始化容器：

```yaml
services:
  opensearch-init:
    image: curlimages/curl:latest
    depends_on:
      - wazuh.indexer
    volumes:
      - ./ai-agent-project/app/wazuh-alerts-vector-template.json:/template.json
    command: |
      sh -c "
        sleep 30 &&
        curl -X PUT 'https://wazuh.indexer:9200/_index_template/wazuh-alerts-vector-template' \
          -H 'Content-Type: application/json' \
          -u admin:SecretPassword \
          -k \
          -d @/template.json
      "
```

## 驗證修正

### 檢查索引模板
```bash
curl -X GET "https://wazuh.indexer:9200/_index_template/wazuh-alerts-vector-template" \
  -u admin:SecretPassword \
  -k
```

### 檢查索引映射
```bash
curl -X GET "https://wazuh.indexer:9200/wazuh-alerts-*/_mapping/field/alert_vector" \
  -u admin:SecretPassword \
  -k
```

### 測試向量搜尋
```python
# 在 Python 中測試
from opensearchpy import OpenSearch

client = OpenSearch(
    hosts=['https://wazuh.indexer:9200'],
    http_auth=('admin', 'SecretPassword'),
    use_ssl=True,
    verify_certs=False
)

# 測試向量搜尋
test_vector = [0.1] * 768
response = client.search(
    index="wazuh-alerts-*",
    body={
        "query": {
            "knn": {
                "alert_vector": {
                    "vector": test_vector,
                    "k": 5
                }
            }
        }
    }
)
```

## 預防措施

1. **確保索引模板優先套用**：在建立任何 Wazuh 索引之前，先套用向量索引模板
2. **定期驗證**：使用 `verify_vectorization.py` 腳本定期檢查向量化狀態
3. **監控錯誤**：在日誌中監控向量搜尋相關錯誤

## 技術細節

### 正確的欄位映射
```json
{
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
  }
}
```

### 關鍵參數說明
- `type: dense_vector`：定義為密集向量類型
- `dims: 768`：Gemini text-embedding-004 模型的向量維度
- `similarity: cosine`：使用餘弦相似度計算
- `type: hnsw`：使用 HNSW (Hierarchical Navigable Small World) 演算法進行高效搜尋

## 結論

這個錯誤的修正需要重新建立具有正確映射的索引。雖然過程涉及重新索引資料，但這是確保向量搜尋功能正常運作的必要步驟。建議在生產環境中執行前先在測試環境驗證。