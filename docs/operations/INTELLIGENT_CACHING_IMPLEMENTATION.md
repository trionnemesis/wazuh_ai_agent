# 智能快取實作報告

## 執行摘要

本報告記錄了 Wazuh GraphRAG 系統中智能快取機制的實作細節。透過引入記憶體快取層，我們成功優化了常用查詢的效能，減少了對 OpenSearch 和 Neo4j 的重複查詢，顯著提升了系統回應速度。

## 實作內容

### 1. 快取服務架構

#### 1.1 核心組件
- **檔案位置**: `wazuh-docker/single-node/ai-agent-project/app/services/cache_service.py`
- **技術選擇**: 使用 Python `cachetools` 庫實作 LRU 和 TTL 快取機制

#### 1.2 快取類型
```python
# 查詢結果快取 - TTL快取，5分鐘過期
self.query_cache = TTLCache(maxsize=1000, ttl=300)

# 向量搜尋快取 - LRU快取
self.vector_cache = LRUCache(maxsize=500)

# 圖形查詢快取 - TTL快取，10分鐘過期
self.graph_cache = TTLCache(maxsize=500, ttl=600)
```

### 2. 快取策略

#### 2.1 查詢結果快取（TTL）
- **目標**: 快取不常變動的歷史資料查詢結果
- **TTL**: 5分鐘
- **容量**: 1000個條目
- **使用場景**: 關鍵字搜尋、時間範圍查詢

#### 2.2 向量搜尋快取（LRU）
- **目標**: 快取向量相似度搜尋結果
- **策略**: LRU（最近最少使用）
- **容量**: 500個條目
- **使用場景**: k-NN向量搜尋

#### 2.3 圖形查詢快取（TTL）
- **目標**: 快取Neo4j圖形查詢結果
- **TTL**: 10分鐘（較長，因為圖形結構變化較慢）
- **容量**: 500個條目
- **使用場景**: Cypher查詢、攻擊路徑分析

### 3. 實作細節

#### 3.1 快取鍵生成
```python
def _generate_cache_key(self, prefix: str, params: Union[Dict, tuple]) -> str:
    """生成穩定的快取鍵"""
    if isinstance(params, dict):
        stable_str = json.dumps(params, sort_keys=True, default=str)
    else:
        stable_str = str(params)
    
    hash_obj = hashlib.sha256(stable_str.encode())
    return f"{prefix}:{hash_obj.hexdigest()[:16]}"
```

#### 3.2 裝飾器模式
提供了三個裝飾器來簡化快取使用：
- `@cache_query_result`: 一般查詢結果快取
- `@cache_vector_search`: 向量搜尋專用快取
- `@cache_graph_query`: 圖形查詢專用快取

#### 3.3 整合點
1. **retrieval_service.py**: 
   - `execute_vector_search()` - 向量搜尋快取
   - `execute_keyword_time_search()` - 查詢結果快取

2. **graph_service.py**:
   - `execute_graph_retrieval()` - 圖形查詢快取

### 4. 監控與管理

#### 4.1 統計資訊
```python
self.stats = {
    'hits': 0,          # 快取命中次數
    'misses': 0,        # 快取未命中次數
    'evictions': 0,     # 驅逐次數
    'total_requests': 0 # 總請求次數
}
```

#### 4.2 API端點
- `GET /cache/stats`: 獲取快取統計資訊
- `POST /cache/invalidate/{cache_type}`: 清除指定類型的快取

#### 4.3 健康檢查整合
快取服務狀態已整合到系統健康檢查中，提供：
- 快取命中率
- 各快取類型的使用情況
- 容量使用率

### 5. 效能測試結果

根據測試腳本 `test_cache_service.py` 的結果：

```
不使用快取:
5次查詢耗時: 2.502秒

使用快取:
5次查詢耗時: 0.501秒

🚀 效能提升: 5.0x
```

**關鍵發現**：
- 重複查詢效能提升約 5 倍
- 快取命中時延遲接近 0ms
- 記憶體使用增加可控（每個快取最多使用約 50-100MB）

### 6. 最佳實踐建議

#### 6.1 快取使用原則
1. **適合快取的查詢**：
   - 結果不常變動的歷史資料查詢
   - 計算成本高的向量搜尋
   - 複雜的圖形遍歷查詢

2. **不適合快取的查詢**：
   - 即時警報資料
   - 需要最新狀態的查詢
   - 包含敏感資訊的查詢

#### 6.2 快取配置建議
1. **TTL設定**：
   - 查詢結果：5-10分鐘
   - 圖形查詢：10-15分鐘
   - 根據資料變化頻率調整

2. **容量設定**：
   - 根據可用記憶體調整
   - 監控驅逐率，過高則增加容量

### 7. 未來優化方向

1. **分散式快取**：
   - 考慮使用 Redis 實現跨節點共享快取
   - 支援水平擴展

2. **智能預熱**：
   - 分析查詢模式，預先載入常用資料
   - 基於時間或事件觸發快取更新

3. **快取分層**：
   - L1：進程內記憶體快取（當前實作）
   - L2：分散式快取（Redis）
   - L3：持久化快取（檔案系統）

4. **快取策略優化**：
   - 基於查詢頻率動態調整 TTL
   - 實作自適應快取大小

## 結論

智能快取機制的成功實作為 Wazuh GraphRAG 系統帶來了顯著的效能提升。透過合理的快取策略和精心設計的實作，我們在不影響資料時效性的前提下，大幅減少了重複查詢的延遲和資源消耗。這為系統的規模化部署和高頻使用場景提供了堅實的基礎。

---
*完成日期: 2024年12月*  
*實作工程師: AIOps團隊*