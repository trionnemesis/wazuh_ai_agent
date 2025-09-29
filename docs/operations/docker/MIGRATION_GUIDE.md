# Docker 優化遷移指南

本指南協助您從舊的 Docker 設定遷移到優化後的新架構。

## 🎯 遷移概述

### 主要變更

1. **啟動腳本**: `start-unified-stack.sh` → `start-services.sh`
2. **環境變數**: 多個 .env 檔案 → 單一 `.env` 檔案
3. **構建腳本**: `build-images.sh` → `build-images-simplified.sh`
4. **Dockerfile**: 傳統構建 → 多階段構建

## 📋 遷移步驟

### 步驟 1: 備份現有配置

```bash
# 建立備份目錄
mkdir -p backup/$(date +%Y%m%d)

# 備份現有環境變數檔案
cp .env backup/$(date +%Y%m%d)/ 2>/dev/null || true
cp env.example backup/$(date +%Y%m%d)/ 2>/dev/null || true
cp ai-agent-project/.env backup/$(date +%Y%m%d)/ai-agent.env 2>/dev/null || true
cp ai-agent-project/performance-optimization.env backup/$(date +%Y%m%d)/ 2>/dev/null || true

# 備份 Docker 卷
docker run --rm -v wazuh-indexer-data:/data -v $(pwd)/backup:/backup alpine tar czf /backup/wazuh-indexer-data.tar.gz -C /data .
```

### 步驟 2: 停止現有服務

```bash
# 使用舊腳本停止服務
./stop-unified-stack.sh

# 或直接使用 docker-compose
docker-compose -f docker-compose.main.yml down
```

### 步驟 3: 整合環境變數

1. **複製新的環境變數範本**
   ```bash
   cp .env.example .env
   ```

2. **遷移現有設定**
   
   從舊的環境變數檔案遷移您的自定義設定到新的 `.env` 檔案。

   **對應關係：**
   
   | 舊檔案 | 變數 | 新位置 (.env) |
   |--------|------|---------------|
   | ai-agent-project/.env | API 金鑰 | AI Agent 配置區段 |
   | performance-optimization.env | 快取設定 | 快取配置區段 |
   | env.example | 基本設定 | 對應的區段 |

3. **驗證設定**
   ```bash
   # 檢查環境變數是否正確載入
   docker-compose -f docker-compose.main.yml config
   ```

### 步驟 4: 更新 Docker Compose 檔案

如果您有自定義的 `docker-compose.override.yml`，請確保更新環境變數參考：

```yaml
# 舊的寫法
env_file:
  - ./ai-agent-project/.env

# 新的寫法
env_file:
  - ./.env
```

### 步驟 5: 重新構建映像（可選）

如果您想使用優化的 Dockerfile：

```bash
# 使用新的構建腳本
./build-docker-images/build-images-simplified.sh --clean

# 或指定特定版本
./build-docker-images/build-images-simplified.sh -v 4.7.4
```

### 步驟 6: 啟動新系統

```bash
# 使用新的啟動腳本
./start-services.sh

# 檢查服務狀態
docker-compose -f docker-compose.main.yml ps

# 執行健康檢查
./health-check.sh
```

## 🔄 配置遷移對照表

### Wazuh 相關設定

| 舊變數名稱 | 新變數名稱 | 預設值 |
|-----------|-----------|--------|
| WAZUH_MANAGER_PASSWORD | WAZUH_ADMIN_PASSWORD | SecretPassword |
| INDEXER_PASSWORD | WAZUH_INDEXER_PASSWORD | SecretPassword |
| API_USER | WAZUH_API_USERNAME | wazuh-wui |
| API_PASS | WAZUH_API_PASSWORD | MyS3cr37P450r.*- |

### AI Agent 設定

| 舊變數名稱 | 新變數名稱 | 說明 |
|-----------|-----------|------|
| LOG_LEVEL | AI_AGENT_LOG_LEVEL | 日誌等級 |
| WORKERS | AI_AGENT_WORKERS | 工作程序數 |
| ENABLE_CACHE | CACHE_ENABLED | 啟用快取 |
| CACHE_SIZE | CACHE_LRU_MAXSIZE | LRU 快取大小 |

### 效能優化設定

| 功能類別 | 新增變數 | 用途 |
|---------|---------|------|
| 連接池 | OPENSEARCH_MAX_CONNECTIONS | OpenSearch 最大連接數 |
| 批次處理 | EMBEDDING_BATCH_SIZE | 向量化批次大小 |
| 並發控制 | ALERT_PROCESSING_CONCURRENCY | 警報處理並發數 |
| 快取管理 | CACHE_TTL_SECONDS | 快取過期時間 |

## ⚠️ 注意事項

### 1. 資料持久性

遷移過程不會影響 Docker 卷中的資料，但建議先備份重要資料。

### 2. 網路配置

新系統使用相同的網路名稱 (`wazuh-graphrag-net`)，無需更改網路設定。

### 3. 憑證管理

SSL 憑證路徑保持不變：
- Wazuh 憑證: `./config/wazuh_indexer_ssl_certs/`
- 其他憑證: 保持原有路徑

### 4. 自定義腳本

如果您有依賴舊啟動腳本的自定義腳本，需要更新為使用新的腳本：

```bash
# 舊的呼叫方式
./start-unified-stack.sh

# 新的呼叫方式
./start-services.sh
```

## 🔍 驗證遷移

### 1. 檢查服務運行狀態

```bash
# 所有服務應該顯示為 "Up" 狀態
docker-compose -f docker-compose.main.yml ps
```

### 2. 驗證資料完整性

```bash
# 檢查 Wazuh 索引
curl -k -u admin:$WAZUH_ADMIN_PASSWORD https://localhost:9200/_cat/indices

# 檢查 Neo4j 連接
curl http://localhost:7474

# 檢查 AI Agent 健康狀態
curl http://localhost:8000/health
```

### 3. 監控系統指標

- 訪問 Prometheus: http://localhost:9090
- 訪問 Grafana: http://localhost:3000
- 檢查系統資源: `docker stats`

## 🛠️ 故障排除

### 問題 1: 環境變數未正確載入

**症狀**: 服務使用預設密碼而非自定義密碼

**解決方案**:
```bash
# 確認 .env 檔案存在且可讀
ls -la .env

# 驗證變數值
grep "WAZUH_ADMIN_PASSWORD" .env

# 重新載入配置
docker-compose -f docker-compose.main.yml down
docker-compose -f docker-compose.main.yml up -d
```

### 問題 2: 服務依賴問題

**症狀**: AI Agent 在 Neo4j 準備好之前啟動失敗

**解決方案**:
```bash
# 檢查健康檢查狀態
docker inspect wazuh-neo4j-graphrag | grep -A 10 "Health"

# 手動重啟失敗的服務
docker-compose -f docker-compose.main.yml restart ai-agent
```

### 問題 3: 磁碟空間不足

**症狀**: 構建或啟動失敗

**解決方案**:
```bash
# 清理未使用的資源
docker system prune -a

# 檢查磁碟使用情況
docker system df
df -h
```

## 📚 相關文件

- [Docker 優化指南](./DOCKER_OPTIMIZATION_GUIDE.md)
- [健康檢查說明](../wazuh-docker/single-node/README.md)
- [AI Agent 配置指南](../wazuh-docker/single-node/ai-agent-project/README.md)

## 💡 最佳實踐建議

1. **分階段遷移**: 先在測試環境驗證，再遷移生產環境
2. **監控遷移過程**: 使用日誌和監控工具追蹤遷移狀態
3. **保留回滾方案**: 保留舊配置檔案直到新系統穩定運行
4. **文件更新**: 更新內部文件以反映新的配置方式

遷移完成後，您將享受到更簡潔、更易維護的 Docker 環境！