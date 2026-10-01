[← 回到 README](../README.md)

# 詳細工作流程與技術架構

## 詳細工作流程

#### 1. 警報生成與索引
- **資料收集**：Wazuh Manager 從各種來源接收日誌和事件
- **規則匹配**：基於預設和自訂規則產生安全警報
- **資料傳輸**：透過 Filebeat 以 SSL 加密方式將警報傳送至 Wazuh Indexer

#### 2. AI 分析引擎
- **定時掃描**：AI Agent 每 60 秒查詢 `wazuh-alerts-*` 索引中未分析的警報
- **智慧篩選**：僅處理不含 `ai_analysis` 欄位的新警報，避免重複分析
- **動態 LLM 選擇**：根據環境變數 `LLM_PROVIDER` 自動選擇 Gemini 或 Claude
- **RAG 上下文檢索**：查詢同主機近期警報，用本機 `sentence-transformers` 模型 embedding 後依語意相似度排序，取 top-k 作為上下文（取代單純的假字串）
- **Agent 決策迴圈**：先請 LLM 判斷現有上下文是否足夠；若判斷不足，才觸發「擴大查詢」——依來源 IP (`data.srcip`) 或規則 ID (`rule.id`) 跨主機找關聯事件，再併入上下文重新分析
- **結構化分析**：使用 LangChain 框架進行提示工程，產生結構化分析報告，並強制輸出可解析的 `RISK_LEVEL` 欄位

#### 3. 分析結果整合
- **即時更新**：分析完成後立即更新原始警報，新增 `ai_analysis` 欄位（含 `risk_level`、`used_broadened_context`）
- **元資料記錄**：包含分析提供商、時間戳記等元資料
- **視覺化展示**：安全分析師可在 Dashboard 中直接查看 AI 註解的警報
- **高風險通知**：`risk_level` 為 Critical/High 時，自動 POST 到 `AI_AGENT_WEBHOOK_URL`（未設定則略過）

## 技術架構詳解

### 核心技術堆疊
| 類別 | 技術 | 版本 | 說明 |
|------|------|------|------|
| **SIEM 平台** | Wazuh | 4.7.4 | 開源安全資訊與事件管理系統 |
| **搜尋引擎** | OpenSearch | - | 基於 Elasticsearch 的分散式搜尋引擎 |
| **容器化** | Docker Compose | 3.7 | 多容器應用程式編排與管理 |
| **AI 框架** | FastAPI | Latest | 高效能 Python Web 框架 |
| | LangChain | Latest | LLM 應用開發與整合框架 |
| | APScheduler | Latest | Python 任務排程函式庫 |
| **LLM 服務** | Google Gemini | 1.5-flash | 快速、經濟的多模態模型 |
| | Anthropic Claude | 3-haiku | 高速、準確的文本分析模型 |
| **網路通訊** | OpenSearch Client | Async | 非同步 OpenSearch 操作 |
| **安全機制** | SSL/TLS | - | 所有服務間通訊加密 |

### Docker 服務架構
```yaml
# 主要服務組成 (docker-compose.yml + docker-compose.override.yml)
services:
  wazuh.manager:     # 主控台 - 警報生成與代理管理
  wazuh.indexer:     # 資料索引 - OpenSearch 後端
  wazuh.dashboard:   # 前端介面 - 視覺化與查詢
  ai-agent:          # AI 分析 - 自動警報分析
```

### AI Agent 內部架構
```python
# 關鍵元件
├── LLM 選擇器 (get_llm())          # 動態選擇 Gemini/Claude
├── Embedding 模型 (sentence-transformers)  # RAG 上下文相似度排序，無需額外向量資料庫
├── 決策鏈 (decision_chain)        # agent 判斷是否需要擴大查詢
├── LangChain 分析鏈              # 提示模板 + LLM + 輸出解析
├── OpenSearch 非同步客戶端        # 與 Wazuh Indexer 通訊 (含窄/廣兩種上下文查詢)
├── Webhook 通知 (aiohttp)        # 高風險警報自動通知
├── APScheduler 排程器           # 每 60 秒執行分析任務
└── FastAPI Web 服務            # 健康檢查與狀態監控
```
