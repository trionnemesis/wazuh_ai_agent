# 目錄結構

```
security-agent-system/
├── apps/
│   ├── cli/                # 基於 Click 的 CLI 進入點
│   ├── langserve/          # LangServe FastAPI 部署
│   └── mcp/                # 模型內容協定（Model Context Protocol）伺服器
├── config/                 # 環境範本與執行階段設定
├── examples/               # 用於示範的範例警報與工作流程
├── requirements.txt        # 專案依賴項 (LangChain, LangGraph, LangServe, MCP)
├── security_agent_system/
│   ├── agents/             # 管理者、獵人、執行者代理的實作
│   ├── core/               # 設定、領域模型、列舉
│   ├── infrastructure/     # 訊息代理、資料庫、通知橋接
│   ├── services/           # 支援服務（操作執行器、協調輔助工具）
│   └── workflows/
│       └── langgraph/      # LangGraph 有向無環圖（DAG）、節點與協調器
├── tests/                  # 涵蓋代理行為的 Pytest 測試套件
└── start.sh                # 用於容器化部署的啟動輔助腳本
```

### 所有權地圖
- **工作流程工程** – `security_agent_system/workflows/langgraph`
- **執行階段服務** – `apps/langserve`, `apps/mcp`
- **核心領域模型** – `security_agent_system/core`
- **基礎設施整合** – `security_agent_system/infrastructure`
- **營運工具** – `docs/operations` 和 `docs/guides`

### 主要進入點
- CLI: `python security-agent-system/main.py ...`
- LangServe API: `uvicorn apps.langserve.app:app --reload`
- MCP 伺服器: `python -m apps.mcp.server`