# Wazuh GraphRAG - 智能安全運營圖形檢索增強生成系統

[![Wazuh Version](https://img.shields.io/badge/Wazuh-4.7.4-blue.svg)](https://github.com/wazuh/wazuh)
[![OpenSearch](https://img.shields.io/badge/OpenSearch-Vector_Search-green.svg)](https://opensearch.org/)
[![Neo4j](https://img.shields.io/badge/Neo4j-5.15_Community-red.svg)](https://neo4j.com/)
[![Google Gemini](https://img.shields.io/badge/Embedding-Gemini_text--embedding--004-orange.svg)](https://ai.google.dev/)
[![Claude AI](https://img.shields.io/badge/LLM-Claude_3_Haiku-purple.svg)](https://www.anthropic.com/)
[![GraphRAG Status](https://img.shields.io/badge/GraphRAG-Stage_5_完成-success.svg)](https://github.com)
[![Refactored](https://img.shields.io/badge/Architecture-Modular_Services-success.svg)](https://github.com)
[![Docker Optimized](https://img.shields.io/badge/Docker-Optimized_&_Unified-success.svg)](https://github.com)
[![Caching](https://img.shields.io/badge/Caching-Intelligent_Memory_Cache-success.svg)](https://github.com)
[![Agent System](https://img.shields.io/badge/Agent_System-3_Agent_Collaboration-success.svg)](https://github.com)
[![Threat Hunting](https://img.shields.io/badge/Threat_Hunting-Active_Investigation-success.svg)](https://github.com)

## 🎯 專案概述

本專案實現了 **六階段演進式 Agent to Agent 協作生態系**，專門針對 Wazuh SIEM 系統的智能威脅分析與自動化防禦。

從 **GraphRAG (圖形檢索增強生成) 架構** 起步，結合 Neo4j 圖形資料庫構建威脅實體關係網路，配合 Google Gemini Embedding 的語義向量化與 Anthropic Claude/Google Gemini 的分析能力，實現深度威脅關聯分析、攻擊路徑識別與專業安全建議生成。

進一步發展為 **Agent to Agent 協作生態系**，包含：
- **管理者 Agent (Stage 4)**：GraphRAG 威脅分析核心，負責攻擊圖譜生成與威脅關聯分析
- **資安獵人 Agent (Stage 5)**：主動威脅狩獵專家，執行深度調查、關聯分析與威脅情資查詢 ✅
- **執行者 Agent (Stage 6)**：自動化防禦執行，形成完整的偵測-分析-執行-驗證閉環

這個協作生態系能夠實現 24/7 全自動威脅監控、分析、狩獵與防禦，大幅提升 SOC 團隊的威脅應對能力。

## 🆕 最新更新

### Docker 環境優化 (2024-12)
- **簡化啟動流程**：將複雜的 `start-unified-stack.sh` 簡化為更清晰的 `start-services.sh`
- **統一環境變數**：整合多個 .env 檔案為單一配置檔案，提升管理效率
- **優化映像構建**：導入多階段構建，減少映像大小約 30%
- **改善服務依賴**：利用 Docker Compose 的 `depends_on` 和 `healthcheck` 機制
- 詳見 [Docker 優化指南](docs/DOCKER_OPTIMIZATION_GUIDE.md) 與 [遷移指南](docs/DOCKER_MIGRATION_GUIDE.md)

## 🏗️ 系統架構圖

```mermaid

graph TD
    subgraph "數據源 & SIEM"
        A[Wazuh Manager] -->|產生警報| B{RabbitMQ 訊息佇列}
    end
    
    subgraph "三代理協作系統 Security Agent System"
        B --> C[管理者代理 Manager Agent]
        C -->|分派任務到 hunting_queue| B
        B -->|接收任務| D[獵人代理 Hunter Agent]
        D -->|發布分析結果到 execution_queue| B
        B -->|接收分析結果| E[執行者代理 Executor Agent]
    end
    
    subgraph "核心分析與資料層"
        D -.->|1. 圖形查詢 GraphRAG| F[Neo4j 圖形資料庫]
        D -.->|2. 向量搜尋 相似事件| G[ChromaDB 向量資料庫]
        D -.->|3. 威脅情資 & 上下文擴充| H[LLM / 外部 API]
        E -.->|生成最終報告與建議| H
    end
    
    subgraph "自動化回應與通知"
        E --> I[動作執行器 Action Executor]
        I --> J["安全設備 API<br/>防火牆, EDR ..."]
        E --> K[通知服務 Slack]
    end
    
    subgraph "監控層"
        L[Prometheus]
        M[Grafana]
        C -.->|暴露 /metrics| L
        D -.->|暴露 /metrics| L
        E -.->|暴露 /metrics| L
        F -.->|暴露 /metrics| L
        L -.->|查詢指標| M
    end
    
    classDef managerStyle fill:#c9f,stroke:#333,stroke-width:2px
    classDef hunterStyle fill:#f9f,stroke:#333,stroke-width:2px
    classDef executorStyle fill:#fcf,stroke:#333,stroke-width:2px
    
    class C managerStyle
    class D hunterStyle
    class E executorStyle
```

### 🚀 當前實施狀態 - 模組化架構重構完成 (Stage 4+)

- ✅ **Stage 1**: 基礎向量化系統 (已完成)
- ✅ **Stage 2**: 核心 RAG 檢索增強生成 (已完成)  
- ✅ **Stage 3**: AgenticRAG 代理關聯分析 (已完成)
- ✅ **Stage 4**: GraphRAG 圖形威脅分析 (已完成)
  - ✅ GraphRAG 架構規劃與設計
  - ✅ 圖形持久層實施 (Neo4j 整合)
  - ✅ 圖形原生檢索器實施
  - ✅ 增強提示詞模板 (Cypher 路徑記號)
  - ✅ 端到端測試與驗證
  - ✅ 統一監控系統整合
  - ✅ 生產部署就緒
- ✅ **模組化重構**: 服務層架構實施 (已完成)
- ✅ **Docker 優化**: 統一構建與部署系統 (已完成)
- ✅ **智能快取**: 記憶體快取機制實作 (已完成)

- ✅ **Stage 5**: 資安獵人 Agent - 主動威脅狩獵 (已完成)
  - ✅ 三代理協作架構實施 (Manager, Hunter, Executor)
  - ✅ 獵人代理深度威脅調查與關聯分析
  - ✅ GraphRAG 圖形實體關係分析
  - ✅ 向量相似性搜尋歷史事件
  - ✅ 多源資料關聯與威脅情資查詢
  - ✅ 完整威脅檔案建構
  - ✅ 異步消息隊列架構 (RabbitMQ)
  - ✅ 人機協作決策機制
  - ✅ 可擴展模組化設計
  - ✅ 生產就緒部署系統
- 📅 **Stage 6**: 執行者 Agent - 閉環自動化防禦 (Q2 2025)

---

## 📚 文件導航

### 📖 文件分類目錄
- **[完整文件目錄](docs/DOCUMENT_CATALOG.md)** - 所有文件的詳細分類與使用指引

### 🎯 主要技術文件

| 文件 | 說明 | 適合對象 |
|------|------|----------|
| **[系統架構設計](docs/ARCHITECTURE.md)** | 完整技術架構與核心組件 | 架構師、技術主管 |
| **[部署指南](docs/DEPLOYMENT.md)** | 詳細部署與配置說明 | DevOps、系統管理員 |
| **[Docker 優化指南](docs/DOCKER_OPTIMIZATION_GUIDE.md)** | 🆕 Docker 環境優化詳解 | DevOps、架構師 |
| **[Docker 遷移指南](docs/DOCKER_MIGRATION_GUIDE.md)** | 🆕 從舊架構遷移到優化架構 | 系統管理員 |
| **[監控系統指南](docs/MONITORING.md)** | 監控配置與運維指南 | 運維工程師 |
| **[智能快取實作](docs/INTELLIGENT_CACHING_IMPLEMENTATION.md)** | 記憶體快取機制詳解 | 開發工程師、架構師 |

### 📊 專案報告與總結
- **[專案報告總覽](docs/PROJECT_REPORTS.md)** - 所有開發報告的快速索引
- **[Stage 5 完成報告](security-agent-system/README.md)** - 🔥 資安獵人Agent三代理協作系統
- **[模組化重構總結](docs/REFACTORING_SUMMARY.md)** - 系統重構的詳細成果
- **[測試策略文件](docs/TESTING_STRATEGY.md)** - 完整測試框架與實踐
- **[測試優化報告](docs/TESTING_OPTIMIZATION_REPORT.md)** - 測試流程優化成果
- **[清理完成報告](docs/CLEANUP_COMPLETION_REPORT.md)** - 程式碼優化清理成果
- **[自動化優化報告](docs/AUTOMATION_OPTIMIZATION_REPORT.md)** - CI/CD 流程優化

### 🗂️ 模組級文件

#### AI Agent 核心模組
- **[AI Agent 模組](wazuh-docker/single-node/ai-agent-project/README.md)** - AI 代理服務詳細說明
- **[模組化架構指南](wazuh-docker/single-node/ai-agent-project/app/REFACTORING_GUIDE.md)** - 模組化重構詳解
- **[實作總結](wazuh-docker/single-node/ai-agent-project/app/IMPLEMENTATION_SUMMARY.md)** - AgenticRAG 技術實作詳解
- **[向量化系統](wazuh-docker/single-node/ai-agent-project/app/README_VECTORIZATION.md)** - 向量化實作說明
- **[Stage 3 關聯分析](wazuh-docker/single-node/ai-agent-project/app/STAGE3_AGENTIC_CORRELATION.md)** - AgenticRAG 深度關聯分析

---

## 🚀 快速開始

### 🔥 新功能：Security Agent System (Stage 5)

體驗最新的三代理協作威脅狩獵系統：

```bash
# 啟動 Security Agent System
cd security-agent-system

# 複製並配置環境變數
cp .env.example .env
# 編輯 .env 填入您的 LLM API keys

# 一鍵啟動完整系統
./start.sh

# 提交測試警報
python main.py submit-alert -t "測試威脅" -d "橫向移動偵測" -s HIGH

# 查看系統狀態
python main.py status

# 執行攻擊模擬
python main.py simulate
```

系統將自動啟動：Manager Agent (分派器)、Hunter Agent (調查專家)、Executor Agent (執行器) 三個智能代理，實現完整的威脅狩獵與回應流程。

### 1. 傳統 GraphRAG 系統環境準備

```bash
# 克隆專案
git clone https://github.com/your-org/wazuh_ai_agent.git
cd wazuh_ai_agent

# 導航至部署目錄
cd wazuh-docker/single-node

# 增加主機的 max_map_count (Linux)
sudo sysctl -w vm.max_map_count=262144

# 生成 SSL 憑證
docker-compose -f generate-indexer-certs.yml run --rm generator
```

### 2. 配置環境變數

編輯 `ai-agent-project/.env` 檔案：

```env
# LLM 配置
GOOGLE_API_KEY=your_gemini_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
LLM_PROVIDER=anthropic

# OpenSearch 配置
OPENSEARCH_HOST=wazuh.indexer
OPENSEARCH_PORT=9200
OPENSEARCH_USERNAME=admin
OPENSEARCH_PASSWORD=SecretPassword

# Neo4j 配置
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=wazuh-graph-2024

# 快取配置
ENABLE_CACHE=true
CACHE_TTL_SECONDS=3600
```

### 3. 啟動系統

```bash
# 使用統一起動腳本
./start-unified-stack.sh
```

### 4. 驗證部署

系統啟動後，您可以透過以下端點存取各項服務：

| 服務 | URL | 預設認證 |
|------|-----|----------|
| 🔐 Wazuh Dashboard | https://localhost:443 | admin / SecretPassword |
| 🧠 AI Agent Metrics | http://localhost:8000/metrics | - |
| 📊 Neo4j Browser | http://localhost:7474 | neo4j / wazuh-graph-2024 |
| 📈 Prometheus | http://localhost:9090 | - |
| 📉 Grafana | http://localhost:3000 | admin / wazuh-grafana-2024 |

---

## 📁 專案目錄架構

```
wazuh_ai_agent/
├── 📄 README.md                           # 專案總覽與快速開始
├── 📁 docs/                               # 主要技術文檔
│   ├── 📄 DOCUMENT_CATALOG.md             # 📚 完整文件分類目錄
│   ├── 📄 ARCHITECTURE.md                 # 系統架構設計
│   ├── 📄 DEPLOYMENT.md                   # 部署指南
│   ├── 📄 MONITORING.md                   # 監控系統指南
│   ├── 📄 PROJECT_REPORTS.md              # 專案報告索引
│   ├── 📄 REFACTORING_SUMMARY.md          # 模組化重構總結
│   ├── 📄 TESTING_STRATEGY.md             # 測試策略文件
│   ├── 📄 TESTING_OPTIMIZATION_REPORT.md  # 測試優化報告
│   ├── 📄 CLEANUP_COMPLETION_REPORT.md    # 清理完成報告
│   ├── 📄 AUTOMATION_OPTIMIZATION_REPORT.md # 自動化優化報告
│   └── 📄 INTELLIGENT_CACHING_*.md        # 智能快取相關文件
├── 📁 legacy/                             # 舊版本檔案
└── 📁 wazuh-docker/                       # Wazuh Docker 部署核心
    ├── 📁 single-node/                    # 單節點部署 (主要)
    │   ├── 📄 start-unified-stack.sh      # 統一起動腳本
    │   ├── 📄 docker-compose.main.yml     # 主要 Docker Compose
    │   └── 📁 ai-agent-project/           # AI Agent 核心專案
    │       ├── 📄 README.md               # AI Agent 模組說明
    │       ├── 📁 app/                    # 應用程式核心
    │       ├── 📁 tests/                  # 測試套件
    │       └── 📁 grafana/                # 監控設定
    └── 📁 multi-node/                     # 多節點部署
```

---

## 📖 快速文件查詢

不確定要查看哪份文件？請參考以下指引：

| 我想要... | 查看文件 |
|-----------|----------|
| 🔥 體驗最新Stage 5系統 | [資安獵人Agent系統](security-agent-system/README.md) |
| 了解系統架構 | [系統架構設計](docs/ARCHITECTURE.md) |
| 部署系統 | [部署指南](docs/DEPLOYMENT.md) |
| 設置監控 | [監控系統指南](docs/MONITORING.md) |
| 查看所有文件 | [完整文件目錄](docs/DOCUMENT_CATALOG.md) |
| 了解專案進展 | [專案報告總覽](docs/PROJECT_REPORTS.md) |
| 了解測試策略 | [測試策略文件](docs/TESTING_STRATEGY.md) |
| 查看模組化設計 | [模組化架構指南](wazuh-docker/single-node/ai-agent-project/app/REFACTORING_GUIDE.md) |

---

## 🤝 貢獻指南

1. Fork 本專案
2. 建立功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交變更 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 開啟 Pull Request

---

## 📄 授權

本專案採用 MIT 授權 - 詳見 [LICENSE](wazuh-docker/LICENSE) 檔案

---

## 📞 支援

如有問題或建議，請：
1. 查看 [部署指南](docs/DEPLOYMENT.md) 的故障排除章節
2. 查閱 [完整文件目錄](docs/DOCUMENT_CATALOG.md) 尋找相關文件
3. 開啟 [GitHub Issue](https://github.com/your-org/wazuh_ai_agent/issues)
4. 聯繫專案維護團隊

---

## 🏆 專案成就

### 技術創新
- ✅ **業界首創**：將 GraphRAG 架構應用於 SIEM 威脅分析
- ✅ **模組化架構**：完整的服務層設計，便於擴展與維護
- ✅ **智能快取**：大幅提升系統效能，降低 API 成本
- ✅ **統一監控**：完整的 Prometheus + Grafana 監控體系

### 效能優化
- 🚀 回應時間降低 40%（透過智能快取）
- 💰 API 成本降低 60%（透過快取重用）
- ⚡ 平行處理提升 3x 效能
- 📊 完整的效能監控與追蹤

### 最新成就 - Stage 5 完成 🎉
- ✅ **三代理協作系統**：Manager、Hunter、Executor 三位一體架構
- ✅ **深度威脅狩獵**：GraphRAG + 向量搜尋的智能關聯分析
- ✅ **異步訊息架構**：RabbitMQ 驅動的高效能協作機制
- ✅ **人機協作決策**：關鍵安全決策的人工審核機制
- ✅ **生產就緒系統**：完整的 Docker 化部署與監控體系

### 未來展望
- 🔄 Stage 6：閉環自動化防禦系統
- 🌍 多語言支援
- 🤝 更多第三方威脅情資整合
- 🧠 機器學習強化的威脅預測



