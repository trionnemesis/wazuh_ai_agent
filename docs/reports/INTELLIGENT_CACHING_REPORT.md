# 智能快取實施報告

## 專案資訊
- **專案名稱**: Wazuh GraphRAG AI Agent
- **功能模組**: 向量嵌入智能快取
- **實施日期**: 2024年12月
- **版本**: 2.1

## 實施摘要

本報告記錄了向量嵌入智能快取機制的實施過程。該機制針對 Google Gemini 嵌入服務進行優化，通過 LRU (Least Recently Used) + TTL (Time To Live) 策略實現高效的記憶體快取，顯著提升了系統效能並降低了 API 成本。

## 實施背景

### 問題描述
- 每次警報分析都會觸發對 Gemini API 的即時查詢
- 相同或相似的警報內容重複進行向量化運算
- API 調用成本高，響應延遲影響用戶體驗
- 系統吞吐量受限於外部 API 的速率限制

### 解決方案
實施智能快取機制，對常用的向量嵌入結果進行記憶體快取，減少重複運算。

## 技術架構

### 1. 快取管理器 (CacheManager)

**檔案**: `/workspace/wazuh-docker/single-node/ai-agent-project/app/utils/cache_manager.py`

**核心特性**:
- **LRU 演算法**: 自動淘汰最少使用的快取項目
- **TTL 機制**: 設定快取過期時間，確保資料時效性
- **執行緒安全**: 使用鎖機制確保並發訪問安全
- **統計收集**: 記錄命中率、使用率等關鍵指標

**主要組件**:
```python
class CacheManager:
    def __init__(self, maxsize: int = 1000, ttl: int = 3600, enabled: bool = True)
    def get(self, key: str) -> Optional[Any]
    def set(self, key: str, value: Any) -> None
    def get_stats(self) -> Dict[str, Any]
    def clear(self) -> None
```

### 2. 快取裝飾器

提供兩種裝飾器模式：

**單一嵌入快取** (`@embedding_cache`):
- 用於 `embed_query` 方法
- 對單一文本的向量化結果進行快取

**批次嵌入快取** (`@batch_embedding_cache`):
- 用於 `embed_documents` 方法
- 支援部分快取命中，只對未快取的項目進行計算

### 3. 整合至 GeminiEmbeddingService

**檔案**: `/workspace/wazuh-docker/single-node/ai-agent-project/app/embedding_service.py`

**更新內容**:
- 初始化時創建快取管理器實例
- `embed_query` 和 `embed_documents` 方法整合快取功能
- 新增 `get_cache_stats` 和 `clear_cache` 方法
- 測試連線時暫時停用快取以確保真實測試

## API 端點

### 快取監控 API

**檔案**: `/workspace/wazuh-docker/single-node/ai-agent-project/app/api/cache_stats.py`

**端點列表**:

1. **GET /api/cache/stats**
   - 獲取快取統計資訊
   - 返回命中率、使用率、大小等指標

2. **POST /api/cache/clear**
   - 清空所有快取
   - 用於記憶體管理或強制更新

3. **POST /api/cache/reset-stats**
   - 重置統計計數器
   - 保留快取內容

4. **GET /api/cache/config**
   - 獲取快取配置參數
   - 顯示 maxsize、ttl、enabled 等設定

## 配置參數

### 環境變數

在 `performance-optimization.env` 中配置：

```env
# === 向量化服務優化 ===
EMBEDDING_CACHE_SIZE=1000        # 最大快取項目數
EMBEDDING_CACHE_TTL=3600         # 快取過期時間（秒）
EMBEDDING_CACHE_ENABLED=true     # 是否啟用快取
```

### 預設值
- **最大容量**: 1000 個項目
- **TTL**: 3600 秒（1 小時）
- **狀態**: 啟用

## 效能優化

### 1. 快取鍵值生成
- 使用 SHA256 雜湊確保唯一性
- 只取前 16 個字符以節省記憶體
- 支援前綴以區分不同類型的快取

### 2. 批次處理優化
- 部分快取命中機制
- 只對未快取的項目調用 API
- 保持結果順序的一致性

### 3. 記憶體管理
- LRU 淘汰策略防止記憶體無限增長
- TTL 機制確保舊資料自動清理
- 提供手動清空快取的 API

## 測試覆蓋

### 單元測試

**檔案**: `/workspace/wazuh-docker/single-node/ai-agent-project/tests/test_cache_manager.py`

**測試項目**:
- 快取初始化和配置
- 鍵值生成的一致性
- Get/Set 操作的正確性
- LRU 淘汰機制
- TTL 過期機制
- 快取停用狀態
- 統計資訊收集
- 裝飾器功能
- 批次處理的部分命中

## 預期效益

### 1. 效能提升
- **響應時間**: 快取命中時從 ~500ms 降至 <1ms
- **吞吐量**: 減少 API 調用，提升系統處理能力
- **並發能力**: 快取減輕了 API 速率限制的影響

### 2. 成本節省
- 減少 Gemini API 調用次數
- 對於重複性高的警報場景，可節省 70-90% 的 API 成本

### 3. 系統穩定性
- 減少對外部服務的依賴
- API 故障時仍可使用快取資料
- 降低網路延遲的影響

## 監控指標

### 關鍵指標
1. **命中率** (Hit Rate): 快取命中次數 / 總請求次數
2. **使用率** (Usage Rate): 當前快取大小 / 最大容量
3. **淘汰率** (Eviction Rate): 淘汰次數 / 設置次數

### 建議閾值
- 命中率 > 60% 表示快取有效
- 使用率 > 90% 時考慮增加容量
- 淘汰率 > 20% 時考慮增加容量或減少 TTL

## 最佳實踐

### 1. 容量規劃
- 根據系統記憶體和使用模式調整 `EMBEDDING_CACHE_SIZE`
- 監控使用率，避免過度使用記憶體

### 2. TTL 設定
- 平衡資料新鮮度和快取效益
- 對於穩定的模型，可以設定較長的 TTL
- 模型更新後應清空快取

### 3. 監控和維護
- 定期檢查快取統計
- 監控記憶體使用情況
- 在系統維護時清理快取

## 未來優化建議

### 1. 分散式快取
- 考慮使用 Redis 實現跨節點共享快取
- 支援水平擴展和高可用性

### 2. 智能預載
- 分析使用模式，預先載入常用項目
- 在系統閒置時更新快取

### 3. 快取分層
- 實施多級快取策略
- 熱資料在記憶體，溫資料在 Redis

### 4. 動態調整
- 根據系統負載動態調整快取大小
- 自適應 TTL 基於使用頻率

## 結論

智能快取機制的實施成功地解決了向量嵌入服務的效能瓶頸問題。通過 LRU+TTL 策略，系統在保持資料時效性的同時，顯著提升了響應速度並降低了運營成本。完整的監控和管理 API 確保了系統的可維護性和可觀測性。

## 相關文件

- [效能優化指南](./PERFORMANCE_OPTIMIZATION_GUIDE.md)
- [系統架構文檔](./ARCHITECTURE.md)
- [API 文檔](./API_DOCUMENTATION.md)