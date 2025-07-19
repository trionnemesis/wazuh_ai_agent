# 📊 Wazuh GraphRAG 效能優化指南

## 🎯 效能優化重點領域

### 1. 資料庫查詢優化

#### Neo4j 圖形查詢優化
- ✅ **已實施**：將串行 Cypher 查詢改為並行執行
- 🎯 **效能提升**：預期提升 3-5 倍查詢速度
- 📝 **最佳實踐**：
  ```cypher
  // 使用索引
  CREATE INDEX ON :Alert(id)
  CREATE INDEX ON :IP(address)
  CREATE INDEX ON :User(name)
  
  // 限制返回結果數量
  MATCH (a:Alert)-[r]->(n) 
  WHERE a.severity > 7
  RETURN a, r, n 
  LIMIT 100
  ```

#### OpenSearch 向量查詢優化
- 🔧 **建議配置**：
  ```json
  {
    "index": {
      "knn": true,
      "knn.algo_param.ef_search": 100,
      "knn.algo_param.ef_construction": 200,
      "knn.algo_param.m": 16
    }
  }
  ```

### 2. 並發處理優化

#### 警報批次處理
```python
# 優化後的批次處理配置
ALERT_PROCESSING_CONCURRENCY = 5  # 同時處理的警報數
ALERT_BATCH_SIZE = 10            # 每批次的警報數量
```

#### 非同步任務管理
- 使用 `asyncio.gather()` 並行執行獨立任務
- 實施 semaphore 限制並發數量，避免資源耗盡

### 3. 快取策略

#### 向量快取
```python
# 實施 LRU 快取策略
from functools import lru_cache

@lru_cache(maxsize=1000)
async def get_cached_embedding(text_hash):
    return await embedding_service.embed_query(text)
```

#### 查詢結果快取
- 快取常見查詢模式的結果
- 設定合理的 TTL (Time To Live)

### 4. 資源監控指標

#### 關鍵效能指標 (KPI)
1. **延遲指標**
   - `alert_processing_duration_seconds`：單個警報處理時間
   - `api_call_duration_seconds`：API 調用時間（按階段）
   - `retrieval_duration_seconds`：資料檢索時間

2. **吞吐量指標**
   - `alerts_processed_total`：已處理警報總數
   - `pending_alerts_gauge`：待處理警報數量

3. **錯誤率指標**
   - `alert_processing_errors_total`：處理失敗總數
   - `api_errors_total`：API 調用失敗次數

### 5. Grafana 儀表板配置

#### 效能監控面板
```json
{
  "panels": [
    {
      "title": "警報處理延遲 (P95)",
      "targets": [{
        "expr": "histogram_quantile(0.95, alert_processing_duration_seconds_bucket)"
      }]
    },
    {
      "title": "系統吞吐量",
      "targets": [{
        "expr": "rate(alerts_processed_total[5m])"
      }]
    },
    {
      "title": "API 調用效能",
      "targets": [{
        "expr": "histogram_quantile(0.95, api_call_duration_seconds_bucket) by (stage)"
      }]
    }
  ]
}
```

### 6. 效能調優檢查清單

- [ ] 配置資料庫連接池大小
- [ ] 實施查詢結果快取
- [ ] 優化批次處理大小
- [ ] 設定適當的超時時間
- [ ] 監控記憶體使用情況
- [ ] 定期清理過期資料
- [ ] 使用資料庫索引
- [ ] 實施速率限制

### 7. 故障排除指南

#### 常見效能問題
1. **高延遲問題**
   - 檢查資料庫連接池是否耗盡
   - 確認網路延遲是否正常
   - 檢視是否有慢查詢

2. **記憶體洩漏**
   - 監控 Python 進程記憶體使用
   - 檢查是否有未關閉的連接
   - 使用 memory profiler 分析

3. **API 速率限制**
   - 實施指數退避重試
   - 使用請求隊列管理
   - 考慮使用多個 API 金鑰

### 8. 效能測試建議

```bash
# 壓力測試命令
ab -n 1000 -c 10 http://localhost:8000/health

# 監控資源使用
docker stats ai-agent

# 查看日誌
docker logs -f ai-agent --tail 100
```

## 🚀 持續優化建議

1. **定期效能審查**：每週檢視 Grafana 儀表板，識別效能瓶頸
2. **A/B 測試**：測試不同配置參數的效能影響
3. **容量規劃**：根據歷史資料預測未來資源需求
4. **自動化調優**：實施自適應參數調整機制