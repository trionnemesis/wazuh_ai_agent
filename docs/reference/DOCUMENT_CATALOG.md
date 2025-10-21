# 文件索引

文件依平台分層組織，協助工程、維運與合作夥伴快速找到所需資訊。

---

## 架構與執行

- [平台架構總覽](../architecture/PLATFORM_ARCHITECTURE.md)：系統分層、資料流程、可靠性設計。
- [LangGraph 工作流程解析](../architecture/LANGGRAPH_WORKFLOW.md)：DAG 節點職責、狀態模型與 LCEL 整合。
- [執行服務層說明](../architecture/RUNTIME_SERVICES.md)：CLI、LangServe、MCP 共享的協調與生命週期。

## 操作指南

- [部署指南](../guides/DEPLOYMENT.md)：單節點安裝、設定與生產環境注意事項。
- [監控與告警指引](../guides/MONITORING.md)：指標定義、告警規則與維運流程。
- [LangServe API 部署指引](../guides/LANGSERVE_DEPLOYMENT.md)：API 啟動、調校與排錯。
- [MCP 伺服器操作手冊](../guides/MCP_SERVER_GUIDE.md)：IDE 整合、工具清單與安全建議。

## 營運資源

- [測試策略](../operations/TESTING_STRATEGY.md)：測試分類、CI 流程與覆蓋率指標。
- [智能快取實作摘要](../operations/INTELLIGENT_CACHING_IMPLEMENTATION.md)：快取層架構與效能成果。
- Docker 套件
  - [Docker 遷移指南](../operations/docker/MIGRATION_GUIDE.md)
  - [Docker 最佳化指南](../operations/docker/OPTIMIZATION_GUIDE.md)
  - [Docker 優化總結](../operations/docker/OPTIMIZATION_SUMMARY.md)

## 報告與紀錄

- [專案報告索引](../reports/PROJECT_REPORTS.md)：歷史交付與重要結論。
- [重構成果摘要](../reports/REFACTORING_SUMMARY.md)：程式碼整併與技術負債處理概況。
- [自動化優化報告](../reports/AUTOMATION_OPTIMIZATION_REPORT.md)
- [清理完成報告](../reports/CLEANUP_COMPLETION_REPORT.md)
- [智能快取報告](../reports/INTELLIGENT_CACHING_REPORT.md)
- [測試優化報告](../reports/TESTING_OPTIMIZATION_REPORT.md)

## 參考

- [目錄結構說明](DIRECTORY_STRUCTURE.md)：程式碼所有權與模組位置。
- [變更紀錄](../reports/REFACTORING_SUMMARY.md#changelog)：近期迭代重點。

---

### 建議閱讀路徑

- **新進工程師**：依序閱讀架構文件、部署指南，再實作 LangServe 部署。
- **維運團隊**：聚焦於監控指引、MCP 操作與 Docker 文件。
- **整合夥伴**：參考目錄結構與 Runtime 文件，瞭解可用 API 與擴充點。
