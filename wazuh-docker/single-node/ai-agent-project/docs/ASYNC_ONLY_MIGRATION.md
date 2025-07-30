# 異步版本遷移指南

## 概述

為了解決 "Timeout context manager should be used inside a task" 錯誤，系統已完全遷移到異步版本。所有同步任務調度代碼已被移除或註解。

## 變更摘要

### 1. 排程器變更

- **移除**: `triage_new_alerts_sync` 函數及其相關調用
- **保留**: `triage_new_alerts` 異步函數
- **排程器**: 現在只使用 `AsyncIOScheduler` 和異步任務包裝器

### 2. 主要文件變更

#### app/main.py
- 新創建的文件，僅作為向後兼容層
- 直接導入 `main_new.py` 中的應用程序

#### app/main_new.py
- 主應用程序入口點
- 使用異步生命週期管理 (`lifespan`)
- 在異步上下文中初始化排程器

#### app/core/scheduler.py
- 只保留異步任務包裝器 `async_job_wrapper`
- 確保排程器在正確的事件循環中運行

### 3. 服務層變更

所有服務現在都使用異步函數：
- `query_new_alerts` - 異步查詢新警報
- `triage_new_alerts` - 異步處理警報分流
- `process_single_alert` - 異步處理單個警報

## 部署步驟

### 1. 重新構建 Docker 映像

```bash
cd /workspace/wazuh-docker/single-node
docker-compose -f docker-compose.main.yml build ai-agent
```

### 2. 停止現有容器

```bash
docker-compose -f docker-compose.main.yml stop ai-agent
```

### 3. 刪除舊容器

```bash
docker-compose -f docker-compose.main.yml rm -f ai-agent
```

### 4. 啟動新容器

```bash
docker-compose -f docker-compose.main.yml up -d ai-agent
```

### 5. 驗證部署

檢查日誌確認沒有錯誤：
```bash
docker-compose -f docker-compose.main.yml logs -f ai-agent
```

應該看到類似以下的啟動日誌：
```
2025-01-25 09:12:37,895 - INFO - 🚀 Wazuh GraphRAG AI Agent v4.0 starting up...
2025-01-25 09:12:38,022 - INFO - Added job "async_job_wrapper" to job store "default"
2025-01-25 09:12:38,023 - INFO - ✅ 排程器已在異步上下文中啟動
```

## 故障排除

### 問題：仍然看到 "triage_new_alerts_sync" 錯誤

**原因**: Docker 容器可能使用了緩存的舊版本代碼。

**解決方案**:
1. 完全清理 Docker 構建緩存：
   ```bash
   docker-compose -f docker-compose.main.yml build --no-cache ai-agent
   ```

2. 刪除所有相關的 Docker 映像：
   ```bash
   docker images | grep ai-agent | awk '{print $3}' | xargs docker rmi -f
   ```

### 問題：健康檢查失敗

**原因**: 健康檢查端點現在是異步的。

**解決方案**: 確保健康檢查客戶端支持異步響應，或使用以下命令測試：
```bash
curl http://localhost:8000/health
```

## 性能優化建議

1. **調整排程間隔**: 修改 `SCHEDULER_INTERVAL_SECONDS` 環境變量來調整任務執行頻率

2. **批量處理**: 異步版本支持更高效的批量處理，可以通過調整 `query_new_alerts` 的 `limit` 參數來優化

3. **連接池管理**: 確保 OpenSearch 和 Neo4j 客戶端使用異步連接池

## 監控和日誌

### Prometheus 指標

訪問 `http://localhost:8000/metrics` 查看以下關鍵指標：
- `scheduler_tasks_total` - 排程任務執行次數
- `alerts_processed_total` - 處理的警報總數
- `processing_errors_total` - 處理錯誤總數

### 日誌級別

通過環境變量 `LOG_LEVEL` 調整日誌詳細程度：
- `DEBUG` - 詳細調試信息
- `INFO` - 一般操作信息（默認）
- `WARNING` - 警告信息
- `ERROR` - 只顯示錯誤

## 回滾計劃

如果需要回滾到之前的版本：

1. 恢復舊的 Docker 映像：
   ```bash
   docker-compose -f docker-compose.main.yml down
   docker tag ai-agent:backup ai-agent:latest
   docker-compose -f docker-compose.main.yml up -d
   ```

2. 但請注意，回滾可能會重新引入 "Timeout context manager" 錯誤。

## 長期維護

1. **定期更新依賴**: 特別是 `aiohttp`, `opensearch-py`, 和 `apscheduler`
2. **監控異步任務性能**: 使用 Grafana 儀表板監控任務執行時間和成功率
3. **錯誤處理**: 確保所有異步函數都有適當的錯誤處理和重試機制