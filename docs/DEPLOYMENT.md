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
```

### 步驟 2: 專案設置

```bash
# 克隆專案
git clone https://github.com/your-org/wazuh_ai_agent.git
cd wazuh_ai_agent

# 進入部署目錄
cd wazuh-docker/single-node

# 設定腳本執行權限
chmod +x start-unified-stack.sh
chmod +x stop-unified-stack.sh
chmod +x health-check.sh
```

### 步驟 3: SSL 憑證生成

```bash
# 生成 Wazuh Indexer SSL 憑證
docker-compose -f generate-indexer-certs.yml run --rm generator

# 驗證憑證生成
ls -la config/wazuh_indexer_ssl_certs/
```

### 步驟 4: 環境變數配置

```bash
# 複製環境變數範例
cp ai-agent-project/.env.example ai-agent-project/.env

# 編輯環境變數
nano ai-agent-project/.env
```

#### 必要的環境變數

```env
# API 金鑰配置
GOOGLE_API_KEY=your_actual_gemini_api_key
ANTHROPIC_API_KEY=your_actual_anthropic_api_key

# LLM 提供商選擇
LLM_PROVIDER=anthropic  # 或 'gemini'

# OpenSearch 連接配置
OPENSEARCH_HOST=wazuh.indexer
OPENSEARCH_PORT=9200
OPENSEARCH_USERNAME=admin
OPENSEARCH_PASSWORD=SecretPassword

# Neo4j 圖形資料庫配置
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=wazuh-graph-2024

# GraphRAG 功能配置
ENABLE_GRAPH_PERSISTENCE=true
GRAPH_BATCH_SIZE=100
GRAPH_MAX_ENTITIES_PER_ALERT=50

# 效能調優參數
VECTOR_SEARCH_K=5
GRAPH_TRAVERSAL_DEPTH=3
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=2048
```

### 步驟 5: 啟動服務

#### 方法一：使用統一起動腳本（推薦）

```bash
# 執行統一起動腳本
./start-unified-stack.sh
```

統一起動腳本會自動執行以下步驟：
1. 檢查系統需求
2. 生成 SSL 憑證（如果不存在）
3. 啟動所有 Docker 服務
4. 等待服務健康檢查
5. 顯示服務狀態和訪問資訊

#### 方法二：手動 Docker Compose 部署

```bash
# 啟動主要服務
docker-compose -f docker-compose.main.yml up -d

# 檢查服務狀態
docker-compose -f docker-compose.main.yml ps

# 查看啟動日誌
docker-compose -f docker-compose.main.yml logs -f
```

### 步驟 6: 服務驗證

```bash
# 執行健康檢查腳本
./health-check.sh

# 手動驗證各服務
curl -f http://localhost:8000/health  # AI Agent
curl -f http://localhost:9090/-/healthy  # Prometheus
curl -f http://localhost:3000/api/health  # Grafana
```

---

## 配置說明

### Docker Compose 配置

#### 主要配置文件

```yaml
# docker-compose.main.yml
version: '3.8'
services:
  wazuh.manager:
    image: wazuh.manager:4.7.4
    ports:
      - "1514:1514"
      - "1515:1515"
      - "514:514/udp"
      - "55000:55000"
    
  wazuh.indexer:
    image: wazuh.indexer:4.7.4
    ports:
      - "9200:9200"
    environment:
      - node.name=wazuh.indexer
      - cluster.initial_master_nodes=wazuh.indexer
      - cluster.name=wazuh-cluster
      - network.host=0.0.0.0
      - discovery.type=single-node
      - OPENSEARCH_JAVA_OPTS=-Xms1g -Xmx1g
    
  wazuh.dashboard:
    image: wazuh.dashboard:4.7.4
    ports:
      - "443:443"
    environment:
      - OPENSEARCH_HOSTS=https://wazuh.indexer:9200
      - WAZUH_API_URL=https://wazuh.manager
    
  ai-agent:
    build:
      context: ./ai-agent-project
      target: production
    ports:
      - "8000:8000"
    environment:
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    depends_on:
      - wazuh.indexer
      - neo4j
    
  neo4j:
    image: neo4j:5.15-community
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      - NEO4J_AUTH=neo4j/wazuh-graph-2024
      - NEO4J_dbms_memory_heap_max__size=4G
      - NEO4J_dbms_memory_pagecache_size=1G
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
      - neo4j_import:/var/lib/neo4j/import
      - neo4j_plugins:/plugins
```

### AI Agent 配置

#### 核心配置參數

```python
# app/core/config.py
class Config:
    # LLM 配置
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    
    # OpenSearch 配置
    OPENSEARCH_HOST = os.getenv("OPENSEARCH_HOST", "wazuh.indexer")
    OPENSEARCH_PORT = int(os.getenv("OPENSEARCH_PORT", "9200"))
    OPENSEARCH_USERNAME = os.getenv("OPENSEARCH_USERNAME", "admin")
    OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD", "SecretPassword")
    
    # Neo4j 配置
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "wazuh-graph-2024")
    
    # GraphRAG 配置
    ENABLE_GRAPH_PERSISTENCE = os.getenv("ENABLE_GRAPH_PERSISTENCE", "true").lower() == "true"
    GRAPH_BATCH_SIZE = int(os.getenv("GRAPH_BATCH_SIZE", "100"))
    GRAPH_MAX_ENTITIES_PER_ALERT = int(os.getenv("GRAPH_MAX_ENTITIES_PER_ALERT", "50"))
    
    # 效能配置
    VECTOR_SEARCH_K = int(os.getenv("VECTOR_SEARCH_K", "5"))
    GRAPH_TRAVERSAL_DEPTH = int(os.getenv("GRAPH_TRAVERSAL_DEPTH", "3"))
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
    LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2048"))
```

### 監控配置

#### Prometheus 配置

```yaml
# config/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'ai-agent'
    static_configs:
      - targets: ['ai-agent:8000']
    scrape_interval: 10s
    
  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']
      
  - job_name: 'neo4j'
    static_configs:
      - targets: ['neo4j:2004']
```

#### Grafana 配置

```yaml
# grafana/provisioning/datasources/prometheus.yml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
```

---

## 驗證部署

### 1. 服務健康檢查

```bash
# 執行完整健康檢查
./health-check.sh

# 檢查各服務狀態
docker-compose -f docker-compose.main.yml ps
```

### 2. 功能驗證

#### Wazuh Dashboard 驗證

```bash
# 訪問 Wazuh Dashboard
curl -k https://localhost:443

# 使用預設認證登入
# 用戶名: admin
# 密碼: SecretPassword
```

#### AI Agent 驗證

```bash
# 檢查 AI Agent 健康狀態
curl http://localhost:8000/health

# 檢查指標端點
curl http://localhost:8000/metrics

# 測試 API 端點
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"test": "alert"}'
```

#### Neo4j 驗證

```bash
# 訪問 Neo4j Browser
curl http://localhost:7474

# 使用預設認證登入
# 用戶名: neo4j
# 密碼: wazuh-graph-2024
```

#### 監控系統驗證

```bash
# 檢查 Prometheus
curl http://localhost:9090/-/healthy

# 檢查 Grafana
curl http://localhost:3000/api/health

# 訪問 Grafana Dashboard
# 用戶名: admin
# 密碼: wazuh-grafana-2024
```

### 3. 效能測試

```bash
# 進入 AI Agent 容器
docker-compose -f docker-compose.main.yml exec ai-agent bash

# 執行效能測試
python /app/performance_test.py

# 執行功能測試
python /app/test_stage3_functionality.py
```

---

## 故障排除

### 常見問題與解決方案

#### 1. 服務啟動失敗

**症狀**: Docker 容器無法啟動或立即退出

**解決方案**:
```bash
# 檢查系統資源
free -h && df -h

# 檢查 Docker 狀態
docker system df
docker system prune -f

# 重新生成憑證
docker-compose -f generate-indexer-certs.yml run --rm generator

# 清理並重新啟動
docker-compose -f docker-compose.main.yml down -v
docker-compose -f docker-compose.main.yml up -d
```

#### 2. Neo4j 連接問題

**症狀**: AI Agent 無法連接到 Neo4j

**解決方案**:
```bash
# 檢查 Neo4j 日誌
docker-compose -f docker-compose.main.yml logs neo4j

# 重置 Neo4j 資料庫
docker-compose -f docker-compose.main.yml down
docker volume rm single-node_neo4j_data
docker-compose -f docker-compose.main.yml up -d

# 檢查 Neo4j 連接
docker-compose -f docker-compose.main.yml exec ai-agent python -c "
import os
from neo4j import GraphDatabase
uri = os.getenv('NEO4J_URI', 'bolt://neo4j:7687')
driver = GraphDatabase.driver(uri, auth=(os.getenv('NEO4J_USER', 'neo4j'), os.getenv('NEO4J_PASSWORD', 'wazuh-graph-2024')))
driver.verify_connectivity()
print('Neo4j connection successful')
"
```

#### 3. AI Agent 分析失敗

**症狀**: 警報分析失敗或返回錯誤

**解決方案**:
```bash
# 檢查 API 金鑰配置
cat ai-agent-project/.env | grep API_KEY

# 測試 API 連接
docker-compose -f docker-compose.main.yml exec ai-agent python /app/verify_vectorization.py

# 查看詳細錯誤日誌
docker-compose -f docker-compose.main.yml logs ai-agent

# 檢查環境變數
docker-compose -f docker-compose.main.yml exec ai-agent env | grep -E "(API_KEY|OPENSEARCH|NEO4J)"
```

#### 4. OpenSearch 連接問題

**症狀**: 無法連接到 OpenSearch

**解決方案**:
```bash
# 檢查 OpenSearch 狀態
docker-compose -f docker-compose.main.yml logs wazuh.indexer

# 測試 OpenSearch 連接
curl -u admin:SecretPassword -k https://localhost:9200/_cluster/health

# 檢查索引模板
curl -u admin:SecretPassword -k https://localhost:9200/_template/wazuh-alerts-vector-template
```

#### 5. 記憶體不足問題

**症狀**: 服務頻繁重啟或效能下降

**解決方案**:
```bash
# 調整 Neo4j 記憶體配置
# 編輯 docker-compose.main.yml
environment:
  - NEO4J_dbms_memory_heap_max__size=2G  # 減少到 2GB
  - NEO4J_dbms_memory_pagecache_size=512M  # 減少到 512MB

# 調整 OpenSearch 記憶體
environment:
  - OPENSEARCH_JAVA_OPTS=-Xms512m -Xmx512m  # 減少到 512MB

# 重新啟動服務
docker-compose -f docker-compose.main.yml down
docker-compose -f docker-compose.main.yml up -d
```

#### 6. SSL 憑證問題

**症狀**: HTTPS 連接失敗

**解決方案**:
```bash
# 重新生成 SSL 憑證
docker-compose -f generate-indexer-certs.yml down -v
docker-compose -f generate-indexer-certs.yml run --rm generator

# 檢查憑證檔案
ls -la config/wazuh_indexer_ssl_certs/

# 重新啟動服務
docker-compose -f docker-compose.main.yml down
docker-compose -f docker-compose.main.yml up -d
```

### 日誌分析

#### 查看服務日誌

```bash
# 查看所有服務日誌
docker-compose -f docker-compose.main.yml logs

# 查看特定服務日誌
docker-compose -f docker-compose.main.yml logs ai-agent
docker-compose -f docker-compose.main.yml logs wazuh.indexer
docker-compose -f docker-compose.main.yml logs neo4j

# 即時監控日誌
docker-compose -f docker-compose.main.yml logs -f ai-agent
```

#### 常見錯誤訊息

1. **Connection refused**: 服務未啟動或端口被佔用
2. **Authentication failed**: API 金鑰或認證資訊錯誤
3. **Out of memory**: 系統記憶體不足
4. **SSL certificate error**: SSL 憑證配置問題
5. **Index not found**: OpenSearch 索引未正確創建

### 效能調優

#### 記憶體優化

```bash
# 調整 Neo4j 記憶體配置
environment:
  - NEO4J_dbms_memory_heap_max__size=4G
  - NEO4J_dbms_memory_pagecache_size=1G

# 調整 OpenSearch 記憶體
environment:
  - OPENSEARCH_JAVA_OPTS=-Xms2g -Xmx2g
```

#### 效能監控

```bash
# 監控系統資源使用
docker stats

# 檢查容器資源限制
docker-compose -f docker-compose.main.yml exec ai-agent top

# 監控 AI Agent 效能指標
curl http://localhost:8000/metrics | grep -E "(alert_processing|api_call)"
```

---

## 進階配置

### 生產環境部署

#### 高可用性配置

```yaml
# 多實例部署
services:
  ai-agent:
    deploy:
      replicas: 3
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
```

#### 安全性配置

```yaml
# 網路隔離
networks:
  wazuh_network:
    driver: bridge
    internal: true

# 資源限制
services:
  ai-agent:
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
```

### 備份與恢復

#### 資料備份

```bash
# 備份 Neo4j 資料
docker-compose -f docker-compose.main.yml exec neo4j neo4j-admin dump --database=neo4j --to=/backups/

# 備份 OpenSearch 資料
curl -u admin:SecretPassword -X POST "https://localhost:9200/_snapshot/backup_repo/snapshot_$(date +%Y%m%d_%H%M%S)?wait_for_completion=true"
```

#### 資料恢復

```bash
# 恢復 Neo4j 資料
docker-compose -f docker-compose.main.yml exec neo4j neo4j-admin load --from=/backups/neo4j.dump --database=neo4j --force

# 恢復 OpenSearch 資料
curl -u admin:SecretPassword -X POST "https://localhost:9200/_snapshot/backup_repo/snapshot_name/_restore"
```

---

## 總結

本部署指南提供了 Wazuh GraphRAG 系統的完整部署流程，從環境準備到服務驗證，涵蓋了所有必要的步驟和配置。通過遵循本指南，您可以成功部署一個功能完整的智能安全運營系統。

對於生產環境部署，建議：
1. 根據實際需求調整硬體配置
2. 實施適當的安全措施
3. 建立監控和備份策略
4. 定期更新和維護系統

如有任何問題，請參考故障排除章節或聯繫技術支援團隊。 