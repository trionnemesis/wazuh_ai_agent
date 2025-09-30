# 執行階段服務總覽

本文件總結了在儲存庫重構期間引入的執行階段層。LangChain、LangGraph、LangServe 和模型內容協定 (MCP) 協同工作，提供多個整合點。

## 服務矩陣

| 服務 | 目的 | 進入點 | 傳輸 | 備註 |
| --- | --- | --- | --- | --- |
| CLI 執行階段 | 操作和本機工作流程 | `apps.cli.main` | 終端機 (Click) | 提供協調指令和管理工具 |
| LangServe API | 用於工作流程的託管 HTTP 介面 | `apps.langserve.app` | FastAPI + LangServe | 將警報處理公開為 LangChain 可執行檔 |
| MCP 伺服器 | IDE 和工具整合 | `apps.mcp.server` | MCP (WebSocket) | 提供從相容用戶端觸發 LangGraph 流程的工具 |

## 生命週期掛鉤

- **啟動**：每個執行階段都會初始化 `LangGraphOrchestrator` 並依需求準備基礎設施連線。共用的初始化邏輯位於 `security_agent_system.workflows.langgraph` 中。
- **關閉**：訊息代理、圖形/向量資料庫和檢查點等資源會透過協調器的拆卸輔助程式關閉。

## 共用元件

- `LangGraphOrchestrator`：跨執行階段重複使用的核心協調器。
- `Agent Nodes`：從 `security_agent_system.workflows.langgraph.agents` 重複使用的管理者、獵人和執行者節點。
- `Settings`：透過 `security_agent_system.core.config.settings` 由 `.env` 驅動的設定。

## 擴充點

- **自訂鏈**：透過圍繞 `LangGraphOrchestrator` 組成 `Runnable` 鏈來擴充 LangServe。
- **MCP 工具**：在 `apps.mcp.server` 中註冊額外的工具定義，以公開新的修復或調查功能。
- **CLI 外掛程式**：在 `apps.cli.main` 中新增 Click 指令，以協調客製化的自動化流程。

完整的套件佈局請參閱 [目錄結構](../reference/DIRECTORY_STRUCTURE.md)。