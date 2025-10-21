# Docker 遷移指南

本指南協助從舊版多腳本部署轉換至精簡的 `docker-compose` 架構。建議先在測試環境驗證再導入生產。

---

## 遷移重點

| 舊實作 | 新實作 | 目的 |
| --- | --- | --- |
| `start-unified-stack.sh` | `docker compose up -d` + 健康檢查 | 減少腳本維護成本 |
| 分散 `.env` 檔案 | 單一 `.env` + `.env.example` | 統一設定來源 |
| 單階段 Dockerfile | 多階段構建 | 降低映像體積 |
| 手動初始化腳本 | 一次性 Job / volume 初始化 | 清晰職責劃分 |

---

## 遷移步驟

1. **備份現有設定**
   ```bash
   mkdir -p backup && cp -r *.env wazuh-docker/single-node docker-compose.* backup/
   docker run --rm -v neo4j-data:/data -v $(pwd)/backup:/backup alpine tar czf /backup/neo4j-data.tgz -C /data .
   ```
2. **停止舊服務**
   ```bash
   docker compose -f docker-compose.main.yml down
   ```
3. **合併環境變數**
   ```bash
   cp .env.example .env
   # 將舊檔案中自訂的金鑰、密碼與效能參數搬至新的 .env 區段
   ```
4. **更新自訂 Compose**
   - 將所有 `env_file` 指向 `.env`。
   - 若有額外服務，確認依賴條件使用 `condition: service_healthy`。
5. **（選擇性）重新構建映像**
   ```bash
   docker compose build --no-cache ai-agent
   ```
6. **啟動並驗證**
   ```bash
   docker compose -f docker-compose.main.yml up -d
   docker compose -f docker-compose.main.yml ps
   curl http://localhost:8001/health
   ```

---

## 設定對照

| 類別 | 關鍵變數 | 新位置說明 |
| --- | --- | --- |
| LLM / LangGraph | `DEFAULT_LLM_PROVIDER`、`LANGSMITH_API_KEY` | `.env` 中 LangGraph 區段 |
| Neo4j | `NEO4J_URI`、`NEO4J_AUTH`、記憶體參數 | `.env` 中資料層區段 |
| 監控 | `PROMETHEUS_SCRAPE_PORT`、`GF_SECURITY_ADMIN_PASSWORD` | `.env` 中監控區段 |
| 安全 | `MCP_SERVER_TOKEN`、`LANGSERVE_TLS_CERT` | `.env` 中安全區段 |

---

## 驗證清單

- `docker compose ps` 全數為 `Up`。
- `curl http://localhost:8001/runtime/status` 顯示 orchestrator 就緒。
- Neo4j Browser (`http://localhost:7474`) 可登入且圖資料存在。
- Grafana 儀表板已連結 Prometheus。

---

## 常見問題

| 情況 | 排查 |
| --- | --- |
| 服務啟動失敗 | 檢查 `.env` 是否缺少必要變數，觀察 `docker compose logs <service>` |
| 無法連至 Neo4j | 確認 `NEO4J_AUTH` 與 volume 尚存；若需回復，解壓備份 tarball |
| 指標缺失 | 檢查 Prometheus job 是否對應新服務名稱 |
| TLS 相關錯誤 | 驗證 `.env` 中證書路徑與 docker volume 掛載 |

完成以上步驟後，即可運用較簡潔、易維護的容器化架構，同時保留回滾備援方案。
