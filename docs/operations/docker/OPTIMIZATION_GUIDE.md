# Docker 優化指南

本文件說明了 Wazuh GraphRAG 整合監控系統的 Docker 優化改進。

## 📋 目錄

1. [簡化的啟動腳本](#簡化的啟動腳本)
2. [統一環境變數管理](#統一環境變數管理)
3. [優化的映像構建流程](#優化的映像構建流程)
4. [最佳實踐建議](#最佳實踐建議)

## 🚀 簡化的啟動腳本

### 改進內容

我們將原本複雜的 `start-unified-stack.sh` 拆分為更簡潔的架構：

1. **新的啟動腳本** (`start-services.sh`)
   - 移除了內建的健康檢查邏輯
   - 依賴 Docker Compose 的 `depends_on` 和 `healthcheck`
   - 減少了 200+ 行程式碼到約 80 行

### 使用方式

```bash
# 啟動所有服務
./start-services.sh

# 檢查服務健康狀態
./health-check.sh

# 查看服務狀態
docker-compose -f docker-compose.main.yml ps

# 查看服務日誌
docker-compose -f docker-compose.main.yml logs -f [service_name]
```

### 主要優點

- **職責分離**：啟動邏輯與健康檢查分離
- **簡化維護**：減少腳本複雜度
- **更好的錯誤處理**：利用 Docker Compose 內建機制
- **更快的啟動時間**：並行啟動服務

## 🔧 統一環境變數管理

### 改進內容

將分散的環境變數檔案整合為單一的 `.env` 檔案：

**之前的結構：**
```
- .env
- env.example
- ai-agent-project/.env
- .env.template
- performance-optimization.env
```

**優化後的結構：**
```
- .env.example (統一的範本檔案)
- .env (從 .env.example 複製並修改)
```

### 配置檔案結構

新的 `.env.example` 檔案包含所有服務的配置，並按功能分組：

1. **構建與部署配置**
2. **Wazuh 安全配置**
3. **Neo4j 圖形資料庫配置**
4. **Grafana 監控配置**
5. **Prometheus 監控配置**
6. **AI Agent 配置**
7. **資料庫連接池配置**
8. **向量化服務優化**
9. **LLM API 優化**
10. **並發處理配置**
11. **快取配置**
12. **系統資源配置**

### 使用方式

```bash
# 初次設定
cp .env.example .env

# 編輯配置
nano .env

# 啟動服務（自動載入 .env）
./start-services.sh
```

### 環境變數優先級

1. Docker Compose 中的 `environment` 設定（最高優先級）
2. `.env` 檔案中的設定
3. 系統環境變數
4. 預設值（在 `.env.example` 中定義）

## 🏗️ 優化的映像構建流程

### 簡化的構建腳本

新的 `build-images-simplified.sh` 提供更清晰的構建流程：

```bash
# 基本構建
./build-images-simplified.sh

# 指定版本構建
./build-images-simplified.sh -v 4.7.5

# 開發環境構建
./build-images-simplified.sh -e development

# 清理快取並重新構建
./build-images-simplified.sh --clean
```

### 多階段構建 Dockerfile

#### Wazuh Manager 優化

新的 `Dockerfile.optimized` 使用多階段構建：

**構建階段：**
- 下載所有必要的套件
- 準備配置檔案
- 最小化構建工具安裝

**執行階段：**
- 只包含執行必要的依賴
- 減少映像層數
- 優化檔案複製順序
- 內建健康檢查

#### 映像大小比較

| 映像 | 原始大小 | 優化後大小 | 減少百分比 |
|------|----------|------------|------------|
| wazuh-manager | ~1.2GB | ~800MB | ~33% |
| ai-agent | ~500MB | ~350MB | ~30% |

### 構建最佳實踐

1. **使用特定版本標籤**
   ```dockerfile
   FROM ubuntu:focal AS builder  # 而非 ubuntu:latest
   ```

2. **最小化層數**
   ```dockerfile
   # 合併 RUN 命令
   RUN apt-get update && \
       apt-get install -y package1 package2 && \
       apt-get clean && \
       rm -rf /var/lib/apt/lists/*
   ```

3. **利用構建快取**
   - 將不常變動的指令放在前面
   - 將應用程式碼複製放在最後

4. **安全性考量**
   - 使用非 root 使用者執行
   - 只安裝必要的套件
   - 清理臨時檔案

## 📊 最佳實踐建議

### 1. 服務依賴管理

在 `docker-compose.main.yml` 中正確設定服務依賴：

```yaml
services:
  ai-agent:
    depends_on:
      wazuh.indexer:
        condition: service_healthy
      neo4j:
        condition: service_healthy
```

### 2. 健康檢查配置

為每個服務配置適當的健康檢查：

```yaml
healthcheck:
  test: ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 60s
```

### 3. 資源限制

設定適當的資源限制以避免資源耗盡：

```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 4G
    reservations:
      cpus: '1.0'
      memory: 2G
```

### 4. 日誌管理

配置日誌輪換以避免磁碟空間耗盡：

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

### 5. 網路安全

使用自定義網路而非預設橋接網路：

```yaml
networks:
  wazuh-graphrag-net:
    driver: bridge
    ipam:
      config:
        - subnet: 172.28.0.0/16
```

## 🔍 故障排除

### 常見問題

1. **服務啟動失敗**
   ```bash
   # 檢查服務日誌
   docker-compose -f docker-compose.main.yml logs [service_name]
   
   # 檢查容器狀態
   docker ps -a
   ```

2. **環境變數未載入**
   ```bash
   # 驗證環境變數
   docker-compose -f docker-compose.main.yml config
   
   # 檢查 .env 檔案權限
   ls -la .env
   ```

3. **映像構建失敗**
   ```bash
   # 清理並重試
   ./build-images-simplified.sh --clean
   
   # 檢查 Docker 空間
   docker system df
   ```

### 效能監控

使用內建的監控工具追蹤系統效能：

1. **Prometheus**: http://localhost:9090
2. **Grafana**: http://localhost:3000
3. **Docker 統計**: `docker stats`

## 📝 總結

這些優化改進提供了：

- ✅ 更簡潔的啟動流程
- ✅ 統一的配置管理
- ✅ 更小的 Docker 映像
- ✅ 更好的可維護性
- ✅ 提升的系統效能

持續監控和調整這些配置以適應您的特定需求。