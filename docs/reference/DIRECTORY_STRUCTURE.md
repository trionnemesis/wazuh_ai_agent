# 目錄結構說明

以下為 `security-agent-system/` 儲存庫的主要目錄與職責對應，協助快速定位程式碼與文件。

```
security-agent-system/
├── apps/
│   ├── cli/                # Click 指令介面、批次任務
│   ├── langserve/          # LangServe + FastAPI 入口
│   └── mcp/                # MCP 伺服器與工具定義
├── config/                 # `.env` 範本、部署設定與排程模板
├── docs/                   # 架構、指南、營運報告
├── examples/               # 告警樣本、操作劇本
├── requirements.txt        # 依賴清單
├── security_agent_system/
│   ├── agents/             # Manager / Hunter / Executor 實作與提示鏈
│   ├── core/               # 設定、資料模型、共用邏輯
│   ├── infrastructure/     # Neo4j、Chroma、訊息匯流排、觀測性模組
│   ├── services/           # Playbook 執行器、報告生成等服務
│   └── workflows/
│       └── langgraph/      # DAG 定義、節點、檢查點管理、Orchestrator
├── tests/                  # Pytest 測試套件與夾具
└── start.sh                # 容器化啟動輔助腳本
```

---

## 職責對照

| 領域 | 目錄 | 摘要 |
| --- | --- | --- |
| 工作流程工程 | `security_agent_system/workflows/langgraph` | 定義 DAG、狀態模型、節點與檢查點 | 
| 代理與決策 | `security_agent_system/agents` | 代理邏輯、提示模板、鏈組合 |
| 基礎設施 | `security_agent_system/infrastructure` | 資料庫、快取、排程、觀測性整合 |
| 執行服務 | `apps/cli`, `apps/langserve`, `apps/mcp` | 提供 CLI、API、IDE 工具入口 |
| 文件與營運 | `docs/` | 架構說明、部署指南、報告與測試策略 |

---

## 主要入口指令

- CLI：`python -m apps.cli.main <command>`
- LangServe：`uvicorn apps.langserve.app:app --host 0.0.0.0 --port 8001`
- MCP：`python -m apps.mcp.server --host 127.0.0.1 --port 8765`

此結構有助於保持模組化與可維護性，讓多代理協調、資料層整合與營運文件各司其職。
