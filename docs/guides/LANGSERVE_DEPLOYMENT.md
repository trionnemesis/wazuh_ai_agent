# LangServe API 部署指引

此文件說明如何啟動 `apps.langserve.app`，並提供最佳化建議以支援生產流量。

---

## 必備條件

- Python 3.11 或 Docker 執行環境
- 已建立的 `.env`（可由 `.env.example` 複製）
- Neo4j、Chroma 等依賴服務已可連線
- 至少一組可用的 LLM API 金鑰（OpenAI / Anthropic / Google）

---

## 啟動流程

### 使用 Python
```bash
pip install -r security-agent-system/requirements.txt
uvicorn apps.langserve.app:app --host 0.0.0.0 --port 8001
```

### 使用 Docker Compose
```bash
docker compose -f wazuh-docker/single-node/docker-compose.main.yml up -d ai-agent
```

啟動完成後可訪問：
- OpenAPI：`http://<host>:8001/docs`
- LangServe Playground：`http://<host>:8001/playground`

---

## 主要端點

| 方法 | 路徑 | 說明 |
| --- | --- | --- |
| `POST` | `/alerts/invoke` | 投遞告警，返回代理決策與輸出檔案位置 |
| `GET` | `/health` | 回傳 orchestrator 狀態與依賴服務連線結果 |
| `GET` | `/runtime/status` | 顯示目前的檢查點、排程作業與佇列長度 |
| `GET` | `/metrics` | Prometheus 指標匯出（需啟用對應收集器） |

---

## 調校建議

- **工作進程**：依 CPU 核心調整 `--workers`，常見配置為核心數 ÷ 2。
- **TLS 與反向代理**：建議放置於 NGINX / Envoy 後方統一終止 TLS，並加入速率限制。
- **超時設定**：使用 `UVICORN_TIMEOUT` 環境變數設定長時任務的逾時（預設 120 秒）。
- **後端選項**：可透過 `.env` 切換 RabbitMQ / Redis 作為任務佇列，或改用雲端 Neo4j。

---

## 觀測與稽核

- LangServe 會自動向 Prometheus 暴露 `langgraph_alert_latency_seconds`、`llm_request_tokens_total` 等指標。
- 若設定 `LANGSMITH_API_KEY`，則每次執行都會在 LangSmith 中留下追蹤。
- 服務日誌採用 JSON 結構，位於 `security-agent-system/logs/langserve.log`，方便集中式日誌平台收集。

---

## 常見問題排解

| 現象 | 原因 | 解法 |
| --- | --- | --- |
| 回應 503 | Orchestrator 尚未完成啟動 | 等待背景初始化或檢查 Neo4j 連線 |
| LLM 錯誤 401 | API 金鑰無效或超出配額 | 重新設定金鑰並確認配額狀態 |
| 請求逾時 | Hunter 檢索或 Executor 執行耗時過久 | 提高 `UVICORN_TIMEOUT` 或調整 Playbook | 
| Playground 無法上傳附件 | 未啟用檔案儲存後端 | 設定 `OBJECT_STORAGE_PATH` 或 S3 參數 |

遵循本指引即可快速啟動 LangServe API，並在需要時擴充為高可用的服務節點。
