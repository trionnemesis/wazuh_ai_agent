# 測試策略

本策略文件針對 `security-agent-system` 定義測試分類、覆蓋範疇與自動化流程，以確保 LangGraph 多代理平台的品質與可靠度。

---

## 目標

1. **品質保障**：核心模組（代理節點、GraphRAG、基礎設施）維持 ≥80% 覆蓋率。
2. **穩定營運**：整合測試涵蓋告警生命周期、人工覆核與檢查點復原。
3. **快速回饋**：在開發流程中 5 分鐘內完成單元與冒煙測試。

---

## 測試分類

| 類型 | 標記 | 範圍 | 依賴 | 觸發時機 |
| --- | --- | --- | --- | --- |
| 單元測試 | `@pytest.mark.unit` | 函式、類別、提示鏈後處理 | Mock Neo4j / LLM | 每次提交、自動化 PR | 
| 整合測試 | `@pytest.mark.integration` | LangGraph DAG、檢查點、GraphRAG 互動 | Neo4j / Chroma 測試實例 | 夜間排程、合併前 | 
| 冒煙測試 | `@pytest.mark.smoke` | CLI / LangServe 基本流程 | 模擬依賴 | 每次部署 | 
| 效能測試 | `@pytest.mark.performance` | 批次告警、平行流程 | 可選：Neo4j、LLM 沙箱 | 迭代中或容量規劃 | 
| 安全測試 | `@pytest.mark.security` | 權限、輸入驗證、密鑰管理 | 建議使用隔離環境 | 每季或重大改版 |

---

## 範例

```python
@pytest.mark.unit
def test_manager_plan_generation(valid_alert, manager_node):
    result = manager_node.generate_plan(valid_alert)
    assert result.priority in {"low", "medium", "high"}
    assert result.next_step is not None
```

```python
@pytest.mark.integration
@pytest.mark.requires_neo4j
async def test_full_alert_flow(orchestrator, seeded_graph):
    run_id = await orchestrator.dispatch_alert(alert=seeded_graph.alert)
    result = await orchestrator.wait_for_completion(run_id)
    assert result.status == "completed"
    assert result.manager_decision.step == "executor"
```

---

## 自動化流程

| 階段 | 命令 | 目的 |
| --- | --- | --- |
| 本地開發 | `pytest -m "unit or smoke"` | 快速驗證功能 | 
| CI | `pytest --maxfail=1 --disable-warnings --cov=security_agent_system` | 覆蓋率與品質門檻 | 
| 整合排程 | `pytest -m integration --asyncio-mode=auto` | 驗證真實依賴 | 
| 效能基準 | `pytest -m performance --durations=5` | 收集處理延遲、吞吐量 | 

測試報告透過 `coverage.xml`、`pytest-html` 及 Grafana 「Testing」面板呈現。

---

## 資料夾結構

```
tests/
├── unit/                 # 代理、工具、基礎設施單元測試
├── integration/          # LangGraph DAG、GraphRAG、API 整合測試
├── performance/          # 批次流程與資源壓力測試
├── fixtures/             # 共用樣本資料與假服務
└── conftest.py           # 全域設定與 marker 定義
```

---

## 品質量測

- **覆蓋率**：CI 未達 80% 會標記失敗，整合測試對關鍵模組要求 60% 以上。
- **穩定性**：連續兩次出現 flaky 測試需於 48 小時內修正或隔離。
- **效能基準**：批次 50 筆告警在 90 秒內完成；LLM 單次請求逾時超過 5% 需調查。

---

## 維護節奏

- 每個迭代結束前審視 marker 使用與夾具重用度。
- 新增代理或節點時，同步擴寫單元與整合測試並更新本文件。
- 效能與安全測試至少每季執行一次，並於 `docs/reports/TESTING_OPTIMIZATION_REPORT.md` 留存結果。

透過上述策略，團隊可維持高品質的多代理流程，同時降低回歸風險並加速交付節奏。
