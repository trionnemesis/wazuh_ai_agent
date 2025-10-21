# 執行服務層說明

本文件彙整 `apps/` 目錄所提供的三個執行服務（CLI、LangServe、MCP），並說明它們如何共享 `LangGraphOrchestrator` 與基礎設施。

---

## 服務矩陣

| 服務 | 入口點 | 傳輸協定 | 核心用途 | 主要依賴 |
| --- | --- | --- | --- | --- |
| CLI Runtime | `apps.cli.main:app` | 終端機 / Click | 事件調度、批次操作、維運工具 | Python Click、Rich |
| LangServe API | `apps.langserve.app:app` | HTTP (FastAPI + LangServe) | 將代理流程包裝成 REST / Streaming API | LangServe、Uvicorn |
| MCP Server | `apps.mcp.server:server` | MCP over WebSocket | IDE / Copilot 整合、人工覆核操作 | Model Context Protocol SDK |

三種服務均呼叫 `LangGraphOrchestrator` 的相同方法：
- `start()`：啟動背景工作、排程器與觀測器。
- `dispatch_alert()`：將告警投入 DAG。
- `resume_run()`：從檢查點復原。
- `shutdown()`：釋放 Neo4j、Chroma、LLM session 等資源。

---

## 生命周期流程

1. **啟動**：載入 `.env` 設定，初始化 LLM Provider、Neo4j、Chroma、訊息匯流排與 Prometheus 客戶端。
2. **運行**：依服務類型監聽請求來源（CLI 指令、HTTP 路由或 MCP Tool）。
3. **結束**：註冊 `atexit`／FastAPI shutdown hook 釋放資源並寫入最後一次檢查點。

---

## 共用元件

- **設定管理**：`security_agent_system.core.config.settings` 提供型別安全的設定存取。
- **檢查點儲存**：預設 `SQLiteSaver`，可替換為 `PostgresSaver` 或自訂實作。
- **觀測指標**：`infrastructure.observability` 暴露 Prometheus registry 與日誌格式。
- **背景工作**：排程任務（例如定期同步威脅情報）由 `infrastructure.scheduler` 管理。

---

## 擴充建議

- **新增服務介面**：開發者可依照現有範例建立新的入口模組，只需注入 orchestrator 並處理輸入/輸出轉換。
- **自訂工具**：在 MCP 伺服器中增加工具時，應同步更新 CLI 指令，確保同樣能力可於無 UI 環境使用。
- **部署考量**：
  - CLI 適合容器化為 Batch Job 或以 systemd 管理。
  - LangServe 可橫向擴充並置於 API Gateway 後。
  - MCP 伺服器建議部署於內網，並透過 TLS 與 Token 驗證限制訪問。

這些服務組成了可互補的操作面，讓 SOC 團隊能以腳本、API 或 AI 助手方式調用同一套 LangGraph 安全流程。
