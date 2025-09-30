# MCP 伺服器操作指南

模型內容協定（MCP）伺服器允許 IDE 和命令面板觸發 LangGraph 工作流程。

## 先決條件
- 安裝依賴項：
  ```bash
  pip install -r security-agent-system/requirements.txt
  ```
- 確保網路可存取訊息代理、Neo4j 和 ChromaDB 實例。

## 執行伺服器
```bash
python -m apps.mcp.server --host 0.0.0.0 --port 8765
```

### 旗標
- `--host` – 綁定地址（預設 `127.0.0.1`）。
- `--port` – 用於 MCP 客戶端的 WebSocket 連接埠（預設 `8765`）。

## 可用工具
- `process_alert` – 接受警報負載並返回結構化的 LangGraph 結果。
- `system_status` – 返回用於診斷的協調器健康元資料。

## 與 IDE 整合
1. 設定您的支援 MCP 的 IDE（Cursor、Windsurf 等）以連接到伺服器端點。
2. 如果 IDE 要求，請使用環境變數或本地憑證進行身份驗證。
3. 從 IDE 呼叫 `process_alert` 工具，將警報資料直接發送到 LangGraph。

## 操作技巧
- 監控 Structlog 輸出以追蹤工具呼叫。
- 在進程管理器（systemd、supervisord）後執行以增強彈性。
- 在將伺服器公開到 localhost 之外時使用 TLS 終止。