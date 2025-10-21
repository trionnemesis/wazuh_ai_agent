# MCP 伺服器操作手冊

MCP（Model Context Protocol）伺服器讓支援 MCP 的 IDE 或助理（如 Cursor、Windsurf、VS Code 外掛）可直接呼叫 LangGraph 流程。本手冊涵蓋啟動方式、工具清單與營運建議。

---

## 前置準備

1. 安裝依賴：
   ```bash
   pip install -r security-agent-system/requirements.txt
   ```
2. 設定 `.env` 並確認以下服務可連線：Neo4j、Chroma、訊息匯流排、LLM 提供者。
3. （選用）產生存取憑證：若需遠端存取，建議於反向代理層設定 TLS 與 API Token。

---

## 啟動指令

```bash
python -m apps.mcp.server --host 0.0.0.0 --port 8765
```

常用參數：
- `--host`：綁定位址，預設 `127.0.0.1`。
- `--port`：WebSocket 監聽埠，預設 `8765`。
- `--log-level`：日誌層級，支援 `info`、`debug`。

伺服器啟動後會載入 `LangGraphOrchestrator` 並註冊工具。

---

## 可用工具

| 工具名稱 | 描述 | 主要輸入 | 主要輸出 |
| --- | --- | --- | --- |
| `process_alert` | 將告警投遞至 LangGraph，回傳決策摘要與檢查點資訊 | 告警 JSON、優先度、上下文附件路徑 | Manager / Hunter / Executor 的行動摘要 |
| `system_status` | 查詢執行狀態、排程作業與依賴健康度 | 無 | 服務連線狀態、版本與最近一次告警指標 |
| `approve_execution` | 審批 Executor 提出的行動 | run-id、動作 ID、批註 | 更新後的執行結果與稽核紀錄 |
| `reject_execution` | 駁回並要求補件 | run-id、動作 ID、理由 | 新的 workflow_step 與後續指示 |

---

## 與 IDE 整合

1. 於 IDE 的 MCP 設定頁輸入伺服器位址（例如 `ws://localhost:8765`）。
2. 若 IDE 支援 API Token，將 Token 存於環境變數 `MCP_SERVER_TOKEN` 並於啟動參數 `--auth-token` 使用。
3. 在 IDE 觸發工具：
   - 送出 JSON 告警給 `process_alert` 以啟動調查。
   - 當流程等待人工批准時，會在工具列表顯示 `approve_execution` / `reject_execution`。

---

## 營運建議

- **進程管理**：建議使用 systemd、supervisord 或容器化方式長期運行，並加入自動重啟策略。
- **日誌監控**：日誌位於 `logs/mcp-server.log`，採 JSON 格式，可透過 ELK / Loki 收集。
- **資源配置**：MCP 主要負責訊息轉送，CPU/記憶體需求較低，但需確保與 LangServe 共用的 Neo4j/Chroma 有足夠連線配額。
- **安全性**：若對外服務，必須在反向代理加入 TLS 與來源 IP 白名單；必要時將工具存取限制在指定使用者帳戶。

透過 MCP 伺服器，團隊能在常用的開發與協同工具中直接觸發安全自動化流程，縮短告警處理迴路。
