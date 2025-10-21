# 部署指南

本指南說明如何在單節點環境中部署 `security-agent-system` 及其依賴元件，並提供生產環境調整建議。

---

## 1. 系統需求

### 硬體建議

| 等級 | CPU | 記憶體 | 儲存 | 適用情境 |
| --- | --- | --- | --- | --- |
| 開發 | 4 vCPU | 8 GB | 40 GB SSD | 功能驗證、單人開發 |
| 測試 | 8 vCPU | 16 GB | 80 GB SSD | 團隊整合、壓力測試 |
| 生產 | 16+ vCPU | 32+ GB | 120 GB SSD + 備援 | 24/7 營運 |

### 軟體版本

- Linux x86_64（Ubuntu 22.04 或同級）
- Docker 24+、Docker Compose v2+
- Python 3.11（僅供本地調校）
- Neo4j 5.x、ChromaDB（由容器自帶）

### 網路埠

| 服務 | 預設埠 | 用途 |
| --- | --- | --- |
| LangServe API | 8001 | REST / Streaming 入口 |
| MCP Server | 8765 | IDE / Copilot 工具通道 |
| Prometheus | 9090 | 指標監控 |
| Grafana | 3000 | 儀表板視覺化 |
| Neo4j Bolt/HTTP | 7687 / 7474 | 圖形資料庫 |

---

## 2. 快速開始

1. **擷取程式碼**
   ```bash
   git clone https://github.com/your-org/wazuh_ai_agent.git
   cd wazuh_ai_agent
   ```
2. **準備設定**
   ```bash
   cd security-agent-system
   cp .env.example .env
   ```
   - 依需求填入 LLM API 金鑰、Neo4j 認證、訊息匯流排設定。
3. **啟動服務**
   ```bash
   docker compose -f ../wazuh-docker/single-node/docker-compose.main.yml up -d
   ```
4. **驗證健康狀態**
   ```bash
   docker compose -f ../wazuh-docker/single-node/docker-compose.main.yml ps
   curl http://localhost:8001/health
   ```

---

## 3. 主要服務說明

| 容器 | 角色 | 重要環境變數 |
| --- | --- | --- |
| `ai-agent` | 執行 LangGraph 安全流程 | `DEFAULT_LLM_PROVIDER`、`NEO4J_URI`、`CHROMADB_PATH` |
| `neo4j` | 儲存攻擊圖、節點資訊 | `NEO4J_AUTH`、`NEO4J_dbms_memory_heap_max__size` |
| `prometheus` | 收集代理與系統指標 | `PROMETHEUS_CONFIG` |
| `grafana` | 顯示儀表板 | `GF_SECURITY_ADMIN_PASSWORD` |

環境變數皆集中於 `security-agent-system/.env`，容器啟動時會由 `apps/` 入口載入。

---

## 4. 生產環境調整

### 高可用性

- 將 LangServe 與 MCP 服務拆分至獨立容器或 Kubernetes Deployment，搭配負載平衡。
- Neo4j 可升級至 Aura 或企業版叢集，Chroma 以外部向量儲存替代。

### 安全性

- 於 `.env` 中啟用 TLS 憑證路徑 (`LANGSERVE_TLS_CERT` / `LANGSERVE_TLS_KEY`)。
- MCP 伺服器建議使用長期 Token 並綁定允許的來源 IP。
- 將 `.env` 與備份資料納入秘密管理服務（如 AWS Secrets Manager）。

### 備份策略

- Neo4j：排程 `neo4j-admin dump`，將輸出存入對象儲存。
- Chroma：同步 `CHROMADB_PATH` 目錄或使用外部後端。
- 觀測資料：Grafana 設定 Snapshot 或透過 API 匯出儀表板。

---

## 5. 驗證與回報

1. 透過 CLI 觸發測試告警：
   ```bash
   python -m apps.cli.main test-alert --severity high --type malware "Test alert from deployment"
   ```
2. 在 Grafana 儀表板確認指標：`http://localhost:3000`。
3. 檢查 `security-agent-system/logs/` 中的稽核紀錄，確認流程完成。

---

## 6. 常見問題

| 現象 | 可能原因 | 解法 |
| --- | --- | --- |
| `Connection refused` | 服務尚未啟動或埠被占用 | 檢查 `docker compose ps`，釋放衝突埠 |
| `Invalid API key` | LLM 金鑰錯誤或權限不足 | 重新設定 `.env` 並重啟容器 |
| `Out of memory` | Neo4j / LangGraph 用量過高 | 調整容器記憶體限制或升級方案 |
| `Checkpoint locked` | 先前流程未正常關閉 | 執行 `python -m apps.cli.main resume-run --run-id <id>` |

---

完成上述步驟後，即可在單節點環境中運作完整的 GraphRAG 安全代理平台，並可依實務需求延伸至多節點或雲端部署。
