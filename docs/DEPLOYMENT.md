# Wazuh GraphRAG 部署指南

**版本**: v4.7.4 + GraphRAG Stage 4  
**最後更新**: 2024年12月  
**文件類型**: 部署與配置指南  

---

## 📋 目錄

1. [部署概述](#部署概述)
2. [系統需求](#系統需求)
3. [快速開始](#快速開始)
4. [詳細部署步驟](#詳細部署步驟)
5. [配置說明](#配置說明)
6. [驗證部署](#驗證部署)
7. [故障排除](#故障排除)

---

## 部署概述

本指南涵蓋 Wazuh GraphRAG 整合監控系統的完整部署流程，包括：

- **Wazuh Security Platform** (4.7.4) - SIEM 安全監控
- **AI Agent** - AgenticRAG 智慧警報分析服務
- **Neo4j** (5.15-community) - GraphRAG 圖形資料庫
- **Prometheus** (v2.48.0) - 指標收集與監控
- **Grafana** (10.2.2) - 視覺化儀表板
- **Node Exporter** (v1.7.0) - 系統指標收集

### 部署架構圖

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Wazuh SIEM    │    │    AI Agent      │    │   Neo4j Graph   │
│                 │◄──►│  (AgenticRAG)    │◄──►│   Database      │
│  - Manager      │    │                  │    │                 │
│  - Indexer      │    │  - RAG Analysis  │    │  - Knowledge    │
│  - Dashboard    │    │  - Alert Processing │    │    Graphs      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                        │                        │
         └────────────────────────┼────────────────────────┘
                                  ▼
                    ┌─────────────────────────────┐
                    │     Monitoring Stack        │
                    │                            │
                    │  ┌─────────────┐          │
                    │  │ Prometheus  │          │
                    │  │ (Metrics)   │          │
                    │  └─────┬───────┘          │
                    │        │                  │
                    │  ┌─────▼───────┐          │
                    │  │  Grafana    │          │
                    │  │ (Dashboard) │          │
                    │  └─────────────┘          │
                    └─────────────────────────────┘
```

---

## 系統需求

### 硬體需求

| **組件** | **最低需求** | **推薦配置** | **生產環境** |
|---------|-------------|-------------|-------------|
| **CPU** | 4 核心 | 8 核心 | 16+ 核心 |
| **記憶體** | 8GB | 16GB | 32GB+ |
| **硬碟** | 20GB | 50GB | 100GB+ SSD |
| **網路** | 100Mbps | 1Gbps | 10Gbps |

### 軟體需求

- **作業系統**: Linux (Ubuntu 20.04+, CentOS 8+, RHEL 8+)
- **Docker**: 20.10+
- **Docker Compose**: v2.0+
- **Git**: 最新版本

### 網路需求

- **防火牆**: 開放以下端口
  - 443 (Wazuh Dashboard)
  - 8000 (AI Agent API)
  - 7474 (Neo4j Browser)
  - 9090 (Prometheus)
  - 3000 (Grafana)
  - 9100 (Node Exporter)

---

## 快速開始

### 1. 克隆專案

```bash
git clone https://github.com/your-org/wazuh_ai_agent.git
cd wazuh_ai_agent
```

### 2. 環境準備

```bash
# 導航至部署目錄
cd wazuh-docker/single-node

# 增加主機的 max_map_count (Linux)
sudo sysctl -w vm.max_map_count=262144

# 生成 SSL 憑證
docker-compose -f generate-indexer-certs.yml run --rm generator

# 設定環境變數檔案
cp ai-agent-project/.env.example ai-agent-project/.env
```

### 3. 配置環境變數

編輯 `ai-agent-project/.env` 檔案：

```env
# LLM 配置
GOOGLE_API_KEY=your_gemini_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
LLM_PROVIDER=anthropic  # 或 'gemini'

# OpenSearch 配置
OPENSEARCH_HOST=wazuh.indexer
OPENSEARCH_PORT=9200
OPENSEARCH_USERNAME=admin
OPENSEARCH_PASSWORD=SecretPassword

# Neo4j 配置
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=wazuh-graph-2024

# GraphRAG 功能開關
ENABLE_GRAPH_PERSISTENCE=true
GRAPH_BATCH_SIZE=100
GRAPH_MAX_ENTITIES_PER_ALERT=50
```

### 4. 啟動統一堆疊

```bash
# 授予啟動腳本執行權限
chmod +x start-unified-stack.sh

# 使用啟動腳本（推薦）
./start-unified-stack.sh

# 或手動啟動
docker-compose -f docker-compose.main.yml up -d
```

### 5. 驗證部署

系統啟動後，您可以透過以下端點存取各項服務：

| 服務 | URL | 預設認證 |
|------|-----|----------|
| 🔐 Wazuh Dashboard | https://localhost:443 | admin / SecretPassword |
| 🧠 AI Agent Metrics | http://localhost:8000/metrics | - |
| 📊 Neo4j Browser | http://localhost:7474 | neo4j / wazuh-graph-2024 |
| 📈 Prometheus | http://localhost:9090 | - |
| 📉 Grafana | http://localhost:3000 | admin / wazuh-grafana-2024 |
| 🖥️ Node Exporter | http://localhost:9100 | - |

---

## 詳細部署步驟

### 步驟 1: 系統準備

#### Linux 系統配置

```bash
# 增加虛擬記憶體映射限制
echo 'vm.max_map_count=262144' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p

# 設定 Docker 用戶組
sudo usermod -aG docker $USER
newgrp docker

# 安裝必要套件
sudo apt update
sudo apt install -y docker.io docker-compose git curl
```

#### Windows 系統配置

```powershell
# 安裝 Docker Desktop
# 下載並安裝 Docker Desktop for Windows

# 啟用 WSL2 後端
# 在 Docker Desktop 設定中啟用 WSL2 後端

# 設定記憶體限制
# 在 Docker Desktop 設定中增加記憶體限制至 8GB+
```

### 步驟 2: 憑證生成

```bash
# 生成 SSL 憑證
docker-compose -f generate-indexer-certs.yml run --rm generator

# 驗證憑證生成
ls -la config/wazuh_indexer_ssl_certs/
```

### 步驟 3: 環境配置

#### 基本配置

```bash
# 複製環境變數範本
cp ai-agent-project/.env.example ai-agent-project/.env

# 編輯環境變數
nano ai-agent-project/.env
```

#### 進階配置

在 `ai-agent-project/app/utils/config.py` 中可調整：

```python
# 向量檢索參數
VECTOR_SEARCH_K = 5
VECTOR_SIMILARITY_THRESHOLD = 0.7

# 圖形查詢參數
GRAPH_TRAVERSAL_DEPTH = 3
GRAPH_RESULT_LIMIT = 100

# LLM 參數
LLM_TEMPERATURE = 0.1
LLM_MAX_TOKENS = 2000
```

### 步驟 4: 服務啟動

#### 使用啟動腳本（推薦）

```bash
# 授予執行權限
chmod +x start-unified-stack.sh

# 啟動服務
./start-unified-stack.sh
```

#### 手動啟動

```bash
# 啟動所有服務
docker-compose -f docker-compose.main.yml up -d

# 查看服務狀態
docker-compose -f docker-compose.main.yml ps

# 查看服務日誌
docker-compose -f docker-compose.main.yml logs -f
```

### 步驟 5: 健康檢查

```bash
# 執行健康檢查腳本
./health-check.sh

# 或手動檢查各服務
curl -k https://localhost:443
curl http://localhost:8000/health
curl http://localhost:7474
curl http://localhost:9090
curl http://localhost:3000
```

---

## 配置說明

### 網路配置

所有服務連接到統一網路 `wazuh-graphrag-network`，允許：
- 服務間直接使用服務名稱通訊
- 安全的內部網路隔離
- 統一的服務發現機制

### 資料持久化

以下資料卷提供資料持久化：

```yaml
# Wazuh 相關
- wazuh_etc:/var/ossec/etc
- wazuh_logs:/var/ossec/logs
- wazuh-indexer-data:/var/lib/wazuh-indexer

# Neo4j 相關
- neo4j_data:/data
- neo4j_logs:/logs

# 監控系統相關
- prometheus_data:/prometheus
- grafana_data:/var/lib/grafana
```

### 安全配置

#### SSL/TLS 配置

```yaml
# 自動生成的 SSL 憑證
ssl_certificate: /etc/ssl/certs/wazuh.indexer.pem
ssl_key: /etc/ssl/private/wazuh.indexer-key.pem
ssl_ca: /etc/ssl/certs/root-ca.pem
```

#### 認證配置

```yaml
# Wazuh API
api_username: wazuh-wui
api_password: MyS3cr37P450r.*-

# OpenSearch
indexer_username: admin
indexer_password: SecretPassword

# Neo4j
neo4j_username: neo4j
neo4j_password: wazuh-graph-2024
```

---

## 驗證部署

### 1. 服務狀態檢查

```bash
# 檢查所有容器狀態
docker-compose -f docker-compose.main.yml ps

# 預期輸出
# Name                    Command               State                    Ports
# ---------------------------------------------------------------------------------------
# wazuh-ai-agent         python -m uvicorn app ...   Up             0.0.0.0:8000->8000/tcp
# wazuh-dashboard        /bin/bash /entrypoint.sh    Up             0.0.0.0:443->5601/tcp
# wazuh-indexer          /bin/bash /entrypoint.sh    Up             0.0.0.0:9200->9200/tcp
# wazuh-manager          /bin/bash /entrypoint.sh    Up             0.0.0.0:1514->1514/tcp
# neo4j                  tini -g -- /startup/docker-entrypoint.sh neo4j   Up   0.0.0.0:7474->7474/tcp
# prometheus             /bin/prometheus --config.file=/etc/prometheus/prometheus.yml   Up   0.0.0.0:9090->9090/tcp
# grafana                /run.sh                          Up             0.0.0.0:3000->3000/tcp
# node-exporter          /bin/node_exporter              Up             0.0.0.0:9100->9100/tcp
```

### 2. 功能驗證

#### Wazuh Dashboard 驗證

```bash
# 檢查 Wazuh Dashboard 可訪問性
curl -k -u admin:SecretPassword https://localhost:443/api/agents

# 預期輸出：JSON 格式的代理列表
```

#### AI Agent 驗證

```bash
# 檢查 AI Agent 健康狀態
curl http://localhost:8000/health

# 預期輸出
# {"status": "healthy", "timestamp": "2024-12-XX..."}

# 檢查指標端點
curl http://localhost:8000/metrics

# 預期輸出：Prometheus 格式的指標
```

#### Neo4j 驗證

```bash
# 檢查 Neo4j 連接
curl -u neo4j:wazuh-graph-2024 http://localhost:7474/db/data/

# 預期輸出：Neo4j REST API 回應
```

#### 監控系統驗證

```bash
# 檢查 Prometheus 狀態
curl http://localhost:9090/api/v1/status/targets

# 檢查 Grafana 狀態
curl http://localhost:3000/api/health

# 預期輸出
# {"database":"ok","version":"10.2.2"}
```

### 3. 效能測試

```bash
# 執行效能測試
cd ai-agent-project
python performance_test.py

# 預期輸出：效能指標報告
```

---

## 故障排除

### 常見問題

#### 1. 容器啟動失敗

```bash
# 檢查容器日誌
docker-compose -f docker-compose.main.yml logs <service-name>

# 常見解決方案
# - 檢查記憶體是否足夠
# - 確認端口是否被佔用
# - 驗證環境變數配置
```

#### 2. 網路連接問題

```bash
# 檢查網路配置
docker network ls
docker network inspect wazuh-graphrag-network

# 測試服務間連接
docker exec wazuh-ai-agent ping wazuh.indexer
docker exec wazuh-ai-agent ping neo4j
```

#### 3. 認證錯誤

```bash
# 重置認證
docker-compose -f docker-compose.main.yml down
docker volume rm wazuh-docker_single-node_wazuh-indexer-data
docker-compose -f docker-compose.main.yml up -d
```

#### 4. 效能問題

```bash
# 檢查系統資源
docker stats

# 調整記憶體配置
# 在 docker-compose.main.yml 中增加記憶體限制
```

### 日誌分析

#### 關鍵日誌位置

```bash
# Wazuh Manager 日誌
docker logs wazuh-manager

# AI Agent 日誌
docker logs wazuh-ai-agent

# Neo4j 日誌
docker logs neo4j

# Prometheus 日誌
docker logs prometheus
```

#### 日誌級別調整

```python
# 在 ai-agent-project/app/utils/config.py 中調整
LOG_LEVEL = "DEBUG"  # 或 "INFO", "WARNING", "ERROR"
```

### 備份與恢復

#### 資料備份

```bash
# 備份 Neo4j 資料
docker exec neo4j neo4j-admin dump --database=neo4j --to=/backups/

# 備份 Wazuh 配置
docker cp wazuh-manager:/var/ossec/etc ./backup/wazuh-config

# 備份監控資料
docker cp prometheus:/prometheus ./backup/prometheus-data
```

#### 資料恢復

```bash
# 恢復 Neo4j 資料
docker exec neo4j neo4j-admin load --database=neo4j --from=/backups/

# 恢復 Wazuh 配置
docker cp ./backup/wazuh-config wazuh-manager:/var/ossec/etc
```

---

## 總結

本部署指南涵蓋了 Wazuh GraphRAG 整合監控系統的完整部署流程。通過遵循這些步驟，您可以成功部署一個功能完整的智能安全運營平台。

部署完成後，建議：

1. **定期備份**：建立自動化備份機制
2. **監控維護**：定期檢查系統效能和日誌
3. **安全更新**：保持系統和依賴套件的最新版本
4. **效能調優**：根據實際使用情況調整配置參數

如需進一步協助，請參考專案的其他文件或提交 Issue。 