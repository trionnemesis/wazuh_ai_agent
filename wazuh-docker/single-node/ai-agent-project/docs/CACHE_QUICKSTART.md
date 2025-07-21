# 智能快取快速啟動指南

## 概述

本指南幫助您快速了解和使用 Wazuh GraphRAG 的智能快取功能。

## 快速配置

### 1. 環境變數設置

在 `.env` 文件或 `performance-optimization.env` 中添加：

```bash
# 啟用快取（預設: true）
EMBEDDING_CACHE_ENABLED=true

# 快取大小（預設: 1000）
EMBEDDING_CACHE_SIZE=1000

# 快取 TTL 秒數（預設: 3600）
EMBEDDING_CACHE_TTL=3600
```

### 2. 驗證快取狀態

使用 API 端點檢查快取配置：

```bash
# 獲取快取配置
curl http://localhost:8000/api/cache/config

# 獲取快取統計
curl http://localhost:8000/api/cache/stats
```

## 使用方式

### 自動快取

系統會自動快取所有向量嵌入操作：

1. **單一查詢**: `embed_query()` 方法自動使用快取
2. **批次處理**: `embed_documents()` 支援部分快取命中
3. **警報分析**: `embed_alert_content()` 對相同警報使用快取

### 手動管理

```python
from app.embedding_service import GeminiEmbeddingService

service = GeminiEmbeddingService()

# 獲取快取統計
stats = service.get_cache_stats()
print(f"命中率: {stats['hit_rate']}")

# 清空快取
service.clear_cache()
```

## API 端點

### 監控端點

- `GET /api/cache/stats` - 獲取快取統計資訊
- `GET /api/cache/config` - 獲取快取配置

### 管理端點

- `POST /api/cache/clear` - 清空所有快取
- `POST /api/cache/reset-stats` - 重置統計計數器

## 效能調優

### 1. 調整快取大小

根據記憶體和使用模式調整：

```bash
# 高流量環境
EMBEDDING_CACHE_SIZE=5000

# 記憶體受限環境
EMBEDDING_CACHE_SIZE=500
```

### 2. 調整 TTL

根據資料變化頻率調整：

```bash
# 穩定環境（資料很少變化）
EMBEDDING_CACHE_TTL=7200  # 2 小時

# 動態環境（資料經常變化）
EMBEDDING_CACHE_TTL=1800  # 30 分鐘
```

### 3. 監控指標

關注以下指標：

- **命中率** > 60%: 表示快取有效
- **使用率** > 90%: 考慮增加容量
- **淘汰率** > 20%: 需要增加容量

## 故障排除

### 快取未生效

1. 檢查環境變數是否正確設置
2. 確認 `EMBEDDING_CACHE_ENABLED=true`
3. 檢查日誌中的快取初始化訊息

### 記憶體使用過高

1. 減少 `EMBEDDING_CACHE_SIZE`
2. 減少 `EMBEDDING_CACHE_TTL`
3. 定期清空快取

### 命中率過低

1. 增加 `EMBEDDING_CACHE_SIZE`
2. 分析使用模式，調整 TTL
3. 檢查是否有大量唯一查詢

## 示例腳本

運行演示腳本查看快取效果：

```bash
cd /workspace/wazuh-docker/single-node/ai-agent-project
python examples/cache_demo.py
```

## 最佳實踐

1. **定期監控**: 使用 API 端點監控快取效能
2. **適時清理**: 在系統維護時清空快取
3. **合理配置**: 根據實際使用情況調整參數
4. **測試驗證**: 更改配置後測試系統效能

## 相關資源

- [智能快取實施報告](/workspace/docs/INTELLIGENT_CACHING_REPORT.md)
- [效能優化指南](/workspace/wazuh-docker/single-node/ai-agent-project/docs/PERFORMANCE_OPTIMIZATION_GUIDE.md)
- [API 文檔](/workspace/wazuh-docker/single-node/ai-agent-project/docs/API_DOCUMENTATION.md)