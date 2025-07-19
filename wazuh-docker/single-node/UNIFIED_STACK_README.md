# Wazuh GraphRAG 整合監控系統 - 統一堆疊部署指南

## 📋 概述

本專案整合了以下組件為單一統一的 Docker Compose 堆疊：

- **Wazuh Security Platform** (4.7.4) - 安全資訊與事件管理 (SIEM)
- **AI Agent** - AgenticRAG 智慧警報分析服務
- **Neo4j** (5.15-community) - GraphRAG 圖形資料庫
- **Prometheus** (v2.48.0) - 指標收集與監控
- **Grafana** (10.2.2) - 視覺化儀表板
- **Node Exporter** (v1.7.0) - 系統指標收集

## 🏗️ 架構圖

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

## 🚀 快速開始

### 1. 先決條件

- Docker Engine 20.10+
- Docker Compose v2.0+
- 至少 8GB 可用記憶體
- 20GB 可用硬碟空間

### 2. 環境準備

```bash
# 1. 導航至專案目錄
cd wazuh-docker/single-node

# 2. 生成 SSL 憑證（如果尚未生成）
docker-compose -f generate-indexer-certs.yml run --rm generator

# 3. 設定環境變數檔案
cp ai-agent-project/.env.example ai-agent-project/.env
# 編輯 .env 檔案，設定必要的 API 金鑰

# 4. 授予啟動腳本執行權限
chmod +x start-unified-stack.sh
```

### 3. 啟動統一堆疊

```bash
# 使用啟動腳本（推薦）
./start-unified-stack.sh

# 或手動啟動
docker-compose -f docker-compose.main.yml up -d
```

### 4. 驗證部署

系統啟動後，您可以透過以下端點存取各項服務：

| 服務 | URL | 預設認證 |
|------|-----|----------|
| 🔐 Wazuh Dashboard | https://localhost:443 | admin / SecretPassword |
| 🧠 AI Agent Metrics | http://localhost:8000/metrics | - |
| 📊 Neo4j Browser | http://localhost:7474 | neo4j / wazuh-graph-2024 |
| 📈 Prometheus | http://localhost:9090 | - |
| 📉 Grafana | http://localhost:3000 | admin / wazuh-grafana-2024 |
| 🖥️ Node Exporter | http://localhost:9100 | - |

## 🔧 配置說明

### 環境變數配置

在 `ai-agent-project/.env` 檔案中設定以下關鍵環境變數：

```env
# OpenAI API（用於 LLM 服務）
OPENAI_API_KEY=your_openai_api_key

# OpenSearch 連接設定
OPENSEARCH_HOST=wazuh.indexer
OPENSEARCH_PORT=9200
OPENSEARCH_USERNAME=admin
OPENSEARCH_PASSWORD=SecretPassword

# Neo4j 連接設定（已在 docker-compose 中自動設定）
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=wazuh-graph-2024

# GraphRAG 功能開關
ENABLE_GRAPH_PERSISTENCE=true
GRAPH_BATCH_SIZE=100
GRAPH_MAX_ENTITIES_PER_ALERT=50
```

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

## 📊 監控配置

### Prometheus 指標收集

系統自動收集以下指標：

1. **AI Agent 指標** (`ai-agent:8000/metrics`)
   - 處理請求數量
   - 響應時間
   - 錯誤率
   - GraphRAG 特定指標

2. **系統指標** (`node-exporter:9100`)
   - CPU 使用率
   - 記憶體使用率
   - 磁碟 I/O
   - 網路統計

3. **Neo4j 指標** (`neo4j:2004/metrics`)
   - 資料庫連接數
   - 查詢效能
   - 儲存使用情況

### Grafana 儀表板

預設包含以下儀表板：
- AI Agent 監控儀表板
- 系統資源監控
- Neo4j 效能監控
- Wazuh 整合概覽

## 🛠️ 運維操作

### 服務管理

```bash
# 查看所有服務狀態
docker-compose -f docker-compose.main.yml ps

# 查看特定服務日誌
docker-compose -f docker-compose.main.yml logs -f ai-agent
docker-compose -f docker-compose.main.yml logs -f neo4j
docker-compose -f docker-compose.main.yml logs -f prometheus

# 重啟特定服務
docker-compose -f docker-compose.main.yml restart ai-agent

# 停止所有服務
docker-compose -f docker-compose.main.yml down

# 完全清理（包含資料卷）
docker-compose -f docker-compose.main.yml down -v
```

### 資料備份

```bash
# 備份 Neo4j 資料
docker exec wazuh-neo4j-graphrag neo4j-admin dump --database=neo4j --to=/tmp/neo4j-backup.dump
docker cp wazuh-neo4j-graphrag:/tmp/neo4j-backup.dump ./backups/

# 備份 Grafana 設定
docker exec wazuh-grafana grafana-cli admin export-dashboard > ./backups/grafana-dashboards.json

# 備份 Prometheus 資料
docker exec wazuh-prometheus tar -czf /tmp/prometheus-data.tar.gz /prometheus
docker cp wazuh-prometheus:/tmp/prometheus-data.tar.gz ./backups/
```

### 效能調優

#### Neo4j 記憶體配置

根據系統資源調整 `docker-compose.main.yml` 中的 Neo4j 記憶體設定：

```yaml
environment:
  - NEO4J_dbms_memory_heap_initial_size=2G    # 調整為系統記憶體的 25%
  - NEO4J_dbms_memory_heap_max_size=4G        # 調整為系統記憶體的 50%
  - NEO4J_dbms_memory_pagecache_size=1G       # 調整為系統記憶體的 12.5%
```

#### Prometheus 資料保留

預設保留 30 天的監控資料。如需調整：

```yaml
command:
  - '--storage.tsdb.retention.time=30d'  # 調整保留期間
```

## 🔍 故障排除

### 常見問題

1. **SSL 憑證錯誤**
   ```bash
   # 重新生成憑證
   docker-compose -f generate-indexer-certs.yml run --rm generator
   ```

2. **Neo4j 連接失敗**
   ```bash
   # 檢查 Neo4j 健康狀態
   docker exec wazuh-neo4j-graphrag cypher-shell -u neo4j -p wazuh-graph-2024 "CALL db.ping()"
   ```

3. **AI Agent 無法連接到服務**
   ```bash
   # 檢查網路連接
   docker exec ai-agent curl -I http://neo4j:7474
   docker exec ai-agent curl -k https://wazuh.indexer:9200
   ```

4. **Prometheus 無法抓取指標**
   ```bash
   # 檢查目標狀態
   curl http://localhost:9090/api/v1/targets
   ```

### 日誌分析

```bash
# 檢查啟動順序問題
docker-compose -f docker-compose.main.yml logs --timestamps

# 檢查特定錯誤
docker-compose -f docker-compose.main.yml logs | grep -i error

# 即時監控所有日誌
docker-compose -f docker-compose.main.yml logs -f
```

## 🔒 安全考量

### 生產環境安全建議

1. **更改預設密碼**
   - 修改 Wazuh、Neo4j、Grafana 的預設密碼
   - 使用強密碼策略

2. **SSL/TLS 加密**
   - 確保所有服務間通訊使用 SSL/TLS
   - 定期更新 SSL 憑證

3. **網路安全**
   - 限制對外暴露的連接埠
   - 使用防火牆規則
   - 考慮使用 VPN 或反向代理

4. **資料保護**
   - 定期備份重要資料
   - 加密敏感資料
   - 實施存取控制

## 📚 進階配置

### 自訂 Grafana 儀表板

1. 登入 Grafana (http://localhost:3000)
2. 導入新的儀表板 JSON 檔案
3. 設定自訂警報規則

### 擴展 Prometheus 監控

在 `ai-agent-project/prometheus.yml` 中新增更多監控目標：

```yaml
scrape_configs:
  - job_name: 'custom-service'
    static_configs:
      - targets: ['custom-service:port']
```

### Neo4j 插件配置

在 Neo4j 中安裝額外的插件：

```yaml
environment:
  - NEO4J_PLUGINS=["apoc", "graph-data-science", "neo4j-streams"]
```

## 🤝 支援與貢獻

如遇到問題或需要協助，請：

1. 檢查本文件的故障排除章節
2. 查看 GitHub Issues
3. 提交詳細的錯誤報告，包含：
   - 錯誤訊息
   - 日誌檔案
   - 系統環境資訊
   - 重現步驟

---

**版本**: 1.0  
**最後更新**: 2024-12  
**維護者**: AgenticRAG & GraphRAG 架構工程師