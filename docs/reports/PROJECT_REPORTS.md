# 專案報告索引

彙整 GraphRAG 安全代理平台的重要報告、進度與量測，提供快速導覽。

---

## 核心文件

| 類別 | 內容 | 連結 |
| --- | --- | --- |
| 架構 | 平台整體設計、代理協調、執行層 | [平台架構總覽](../architecture/PLATFORM_ARCHITECTURE.md)、[LangGraph 工作流程解析](../architecture/LANGGRAPH_WORKFLOW.md)、[執行服務層說明](../architecture/RUNTIME_SERVICES.md) |
| 部署 | 單節點部署、LangServe、MCP、監控 | [部署指南](../guides/DEPLOYMENT.md)、[LangServe API 部署指引](../guides/LANGSERVE_DEPLOYMENT.md)、[MCP 伺服器操作手冊](../guides/MCP_SERVER_GUIDE.md)、[監控與告警指引](../guides/MONITORING.md) |
| 營運 | 測試策略、快取機制、Docker 套件 | [測試策略](../operations/TESTING_STRATEGY.md)、[智能快取實作摘要](../operations/INTELLIGENT_CACHING_IMPLEMENTATION.md)、[Docker 文件合集](../operations/docker/OPTIMIZATION_SUMMARY.md) |

---

## 近期重點

- 完成 LangGraph DAG 重構與檢查點持久化，支援人工覆核與錯誤回復。
- GraphRAG 管線整合 Neo4j 與 Chroma，Hunter 節點平均延遲下降 40%。
- LangServe、MCP、CLI 共享同一協調層，部署與維運流程一致。
- 快取層導入後，Neo4j / Chroma 查詢量分別下降 60% / 48%。

---

## 里程碑狀態

| 項目 | 狀態 | 說明 |
| --- | --- | --- |
| Stage 1-3：RAG 基礎與圖形整合 | ✅ 完成 | 向量檢索、圖形遍歷與調查報告 | 
| Stage 4：LangGraph 多代理 | ✅ 完成 | DAG 調度、LCEL 提示鏈、檢查點 | 
| Stage 5：生產最佳化 | 進行中 | 自動化修復擴充、效能監控、容量規劃 |
| Stage 6：持續狩獵與多租戶 | 規劃中 | 長期狩獵任務、租戶隔離 |

---

## 指標快覽（2025 Q1）

| 指標 | 數值 | 備註 |
| --- | --- | --- |
| 告警平均處理時間 | 1.6 秒 | 含三代理協作 | 
| 成功完成率 | 99.2% | 失敗案例可透過檢查點復原 |
| Neo4j 查詢延遲 P95 | 18 毫秒 | 快取命中後 <5 毫秒 |
| LLM Token 節省 | -35% | 快取與決策鏈優化 |

---

## 角色導覽

- **開發人員**：閱讀架構文件 → 了解 LangGraph 節點 → 依 [測試策略](../operations/TESTING_STRATEGY.md) 擴充測試。
- **維運團隊**：依 [部署指南](../guides/DEPLOYMENT.md) 與 Docker 文件部署，透過 [監控與告警指引](../guides/MONITORING.md) 追蹤健康狀態。
- **架構師 / 合作夥伴**：聚焦於平台架構、快取實作與報告文件，評估與既有 SOC 工具整合。

---

## 後續工作

1. 擴充自動化修復模組，支援多雲資產控制與 ITSM 回寫。
2. 建立多租戶授權與資源隔離策略，支援 MSSP 案例。
3. 完成 LangServe、MCP 的壓力測試並更新容量建議。
4. 針對 Stage 6 規劃獵捕任務與長期圖譜分析，於報告中追蹤。

更多細節與歷史紀錄請參考各專題報告與重構摘要。
