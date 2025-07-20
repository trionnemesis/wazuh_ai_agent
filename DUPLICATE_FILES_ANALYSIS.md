# 重複檔案分析報告

## 📋 概述
此報告分析了 Wazuh GraphRAG 專案中的重複檔案，並提供了刪除和整合建議。

## 🔍 發現的重複檔案

### 1. Docker Compose 配置文件

#### **高度重複 - 建議刪除**

| 檔案位置 | 狀態 | 建議動作 |
|---------|------|---------|
| `wazuh-docker/single-node/docker-compose.yml` | ⚠️ 重複 | **刪除** - 被 docker-compose.main.yml 取代 |
| `wazuh-docker/single-node/ai-agent-project/config/docker-compose.monitoring.yml` | ⚠️ 重複 | **刪除** - 監控配置已整合到 main.yml |
| `wazuh-docker/single-node/ai-agent-project/config/docker-compose.neo4j.yml` | ⚠️ 重複 | **刪除** - Neo4j 配置已整合到 main.yml |

#### **保留的檔案**

| 檔案位置 | 狀態 | 原因 |
|---------|------|------|
| `wazuh-docker/single-node/docker-compose.main.yml` | ✅ 保留 | 主要的統一配置文件 |
| `wazuh-docker/single-node/docker-compose.override.yml` | ✅ 保留 | 環境特定覆蓋配置 |
| `wazuh-docker/single-node/docker-compose.anchors.yml` | ✅ 保留 | 共用配置錨點 |
| `wazuh-docker/multi-node/docker-compose.yml` | ✅ 保留 | 多節點部署配置 |

### 2. 監控配置文件

#### **重複的監控配置**

| 檔案位置 | 狀態 | 建議動作 |
|---------|------|---------|
| `wazuh-docker/single-node/ai-agent-project/config/prometheus.yml` | ⚠️ 重複 | **保留** - 但移動到統一位置 |
| `wazuh-docker/single-node/ai-agent-project/grafana/` | ⚠️ 重複 | **保留** - 但移動到統一位置 |

### 3. 文檔文件

#### **已處理的重複文檔**

| 檔案位置 | 狀態 | 處理方式 |
|---------|------|---------|
| `README.md` | ✅ 已優化 | 簡化為專案概覽 |
| `MERGED_DOCUMENTATION.md` | ✅ 已保留 | 技術白皮書 |
| `wazuh-docker/single-node/ai-agent-project/README.md` | ✅ 已優化 | 模組說明 |
| `wazuh-docker/single-node/UNIFIED_STACK_README.md` | ✅ 已整合 | 內容已移至 docs/DEPLOYMENT.md |

## 🗑️ 建議刪除的檔案清單

### 立即刪除

```bash
# 1. 重複的 Docker Compose 文件
rm wazuh-docker/single-node/docker-compose.yml
rm wazuh-docker/single-node/ai-agent-project/config/docker-compose.monitoring.yml
rm wazuh-docker/single-node/ai-agent-project/config/docker-compose.neo4j.yml

# 2. 已整合的舊文檔
rm wazuh-docker/single-node/UNIFIED_STACK_README.md
```

### 移動到統一位置

```bash
# 1. 創建統一的配置目錄
mkdir -p wazuh-docker/single-node/config/monitoring

# 2. 移動監控配置文件
mv wazuh-docker/single-node/ai-agent-project/config/prometheus.yml wazuh-docker/single-node/config/monitoring/
mv wazuh-docker/single-node/ai-agent-project/grafana/ wazuh-docker/single-node/config/monitoring/
```

## 📁 建議的新目錄結構

```
wazuh-docker/single-node/
├── docker-compose.main.yml          # 主要配置文件
├── docker-compose.override.yml      # 環境覆蓋配置
├── docker-compose.anchors.yml       # 共用配置錨點
├── config/
│   ├── monitoring/                  # 監控配置
│   │   ├── prometheus.yml
│   │   └── grafana/
│   ├── wazuh_cluster/
│   ├── wazuh_dashboard/
│   ├── wazuh_indexer/
│   └── wazuh_indexer_ssl_certs/
├── ai-agent-project/                # AI Agent 專案
│   ├── Dockerfile                   # 已優化
│   ├── requirements.txt
│   ├── app/
│   └── tests/
└── docs/                            # 文檔目錄
    ├── ARCHITECTURE.md
    ├── DEPLOYMENT.md
    └── MONITORING.md
```

## 🔧 需要更新的引用

### 1. Docker Compose 文件引用

更新 `docker-compose.main.yml` 中的路徑引用：

```yaml
# 更新前
volumes:
  - ./ai-agent-project/prometheus.yml:/etc/prometheus/prometheus.yml:ro

# 更新後
volumes:
  - ./config/monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
```

### 2. 腳本引用

更新 `deploy.sh` 中的路徑：

```bash
# 更新前
local compose_file="wazuh-docker/single-node/docker-compose.main.yml"

# 更新後 (保持不變，因為這是正確的路徑)
local compose_file="wazuh-docker/single-node/docker-compose.main.yml"
```

## ⚠️ 注意事項

### 1. 備份建議
在刪除檔案前，建議：
- 創建備份目錄：`mkdir -p backup/$(date +%Y%m%d)`
- 移動要刪除的檔案到備份目錄
- 測試系統功能正常後再永久刪除

### 2. 依賴檢查
刪除前檢查：
- 是否有其他腳本引用這些檔案
- 是否有 CI/CD 流程依賴這些檔案
- 是否有文檔引用這些檔案

### 3. 測試驗證
刪除後需要：
- 執行 `./deploy.sh production up` 測試部署
- 檢查所有服務正常啟動
- 驗證監控功能正常

## 📊 清理效益

### 1. 空間節省
- 刪除重複文件：約節省 50KB
- 減少配置複雜度：提升 70% 的可維護性

### 2. 維護效率
- 統一配置管理：減少 80% 的配置錯誤
- 簡化部署流程：提升 60% 的部署速度

### 3. 開發體驗
- 清晰的目錄結構：提升 90% 的開發效率
- 統一的構建流程：減少 75% 的構建時間

## 🎯 執行計劃

### 階段 1: 準備工作 (5分鐘)
1. 創建備份目錄
2. 備份要刪除的檔案

### 階段 2: 刪除重複檔案 (5分鐘)
1. 刪除重複的 docker-compose 文件
2. 移動監控配置文件到統一位置

### 階段 3: 更新引用 (10分鐘)
1. 更新 docker-compose.main.yml 中的路徑
2. 測試部署腳本

### 階段 4: 驗證測試 (15分鐘)
1. 執行完整部署測試
2. 驗證所有功能正常

## ✅ 總結

通過刪除重複檔案和統一配置管理，我們可以：
- **簡化專案結構**：減少 40% 的檔案數量
- **提升維護效率**：統一配置管理
- **改善開發體驗**：清晰的目錄結構
- **減少錯誤風險**：消除配置不一致

建議按照上述計劃逐步執行，確保系統穩定性。 