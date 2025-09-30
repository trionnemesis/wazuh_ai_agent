# 文件目錄

本文件集圍繞新的平台佈局進行組織，該佈局整合了 LangChain、LangGraph、LangServe 和 MCP 的執行時職責。

## 架構與執行環境
- [平台架構](../architecture/PLATFORM_ARCHITECTURE.md) – 核心系統領域、部署拓撲和共享服務。
- [LangGraph 工作流程](../architecture/LANGGRAPH_WORKFLOW.md) – 圖形狀態機、節點職責和 LCEL 使用模式。
- [執行服務](../architecture/RUNTIME_SERVICES.md) – LangServe 和 MCP 服務邊界以及協調生命週期預期。

## 指南與手冊
- [部署指南](../guides/DEPLOYMENT.md) – 端到端安裝和環境配置。
- [監控指南](../guides/MONITORING.md) – 指標、警報和 Grafana 儀表板。
- [LangServe 部署](../guides/LANGSERVE_DEPLOYMENT.md) – 執行由 LangServe 驅動的託管 API。
- [MCP 伺服器操作](../guides/MCP_SERVER_GUIDE.md) – 操作用於 IDE 整合的模型內容協定伺服器。

## 營運工具包
- [測試策略](../operations/TESTING_STRATEGY.md) – 驗證方法和自動化策略。
- [智慧快取實作](../operations/INTELLIGENT_CACHING_IMPLEMENTATION.md) – 快取層和效能考量。
- Docker 手冊
  - [遷移指南](../operations/docker/MIGRATION_GUIDE.md)
  - [優化指南](../operations/docker/OPTIMIZATION_GUIDE.md)
  - [優化總結](../operations/docker/OPTIMIZATION_SUMMARY.md)

## 報告與事後分析
- [專案報告總覽](../reports/PROJECT_REPORTS.md) – 歷史交付成果索引。
- [重構總結](../reports/REFACTORING_SUMMARY.md) – 迭代式程式碼清理的成果。
- [自動化優化報告](../reports/AUTOMATION_OPTIMIZATION_REPORT.md)
- [清理完成報告](../reports/CLEANUP_COMPLETION_REPORT.md)
- [智慧快取報告](../reports/INTELLIGENT_CACHING_REPORT.md)
- [測試優化報告](../reports/TESTING_OPTIMIZATION_REPORT.md)

## 參考
- [目錄結構](DIRECTORY_STRUCTURE.md) – 原始碼樹狀結構佈局和所有權邊界。
- [變更日誌](../reports/REFACTORING_SUMMARY.md#changelog) – 近期迭代的重點。

### 快速入門路徑
- **新進工程師**：檢閱架構三文件，然後遵循部署指南和 LangServe 部署步驟。
- **營運人員**：透過監控指南和 MCP 伺服器操作清單來監控健康狀況。
- **整合人員**：使用目錄結構參考來定位 API、代理和執行時進入點。