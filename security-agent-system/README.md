# Security Agent System - GraphRAG & Agential RAG Hybrid Architecture

一個基於三代理協作的先進資安事件回應系統，結合 GraphRAG 和 Agential RAG 技術。

## 系統架構

本系統將傳統的單一 AI Agent 拆分為三個職責分明、可獨立運作與優化的專業代理：

### 1. 管理者代理 (Manager Agent) - 控制中心
- **核心職責**：接收、分派、追蹤
- **主要功能**：
  - 接收來自 Wazuh、SIEM 等的原始警報
  - 初步分類與去重
  - 創建任務並分派給獵人代理
  - 監控任務生命週期

### 2. 獵人代理 (Hunter Agent) - 調查專家  
- **核心職責**：深度調查、關聯分析、上下文擴充
- **主要功能**：
  - 執行 GraphRAG 分析尋找攻擊路徑
  - 向量相似性搜尋歷史事件
  - 多源資料關聯與威脅情資查詢
  - 建構完整威脅檔案

### 3. 執行者代理 (Executor Agent) - 行動單位
- **核心職責**：綜合分析、生成報告、執行回應
- **主要功能**：
  - 使用強大 LLM 進行最終分析
  - 生成人類可讀的分析報告
  - 提出分級處置建議
  - Human-in-the-Loop 批准機制
  - 執行已批准的安全回應

## 技術特色

- **異步消息隊列架構**：使用 RabbitMQ/Kafka 實現代理間通訊
- **GraphRAG 整合**：Neo4j 圖資料庫進行實體關係分析
- **向量搜尋**：ChromaDB 進行相似事件檢索
- **多 LLM 支援**：可配置使用 OpenAI、Anthropic、Google 模型
- **人機協作**：關鍵決策需要人工批准
- **可擴展性**：每個代理可獨立擴展

## 快速開始

### 環境需求
- Python 3.10+
- Docker & Docker Compose
- API Keys (OpenAI/Anthropic/Google)

### 安裝步驟

1. 複製專案並安裝依賴：
```bash
git clone <repository>
cd security-agent-system
pip install -r requirements.txt
```

2. 設定環境變數：
```bash
cp .env.example .env
# 編輯 .env 填入您的 API keys 和配置
```

3. 啟動基礎設施：
```bash
docker-compose up -d
```

4. 啟動系統：
```bash
python main.py start
```

## 使用方式

### 提交警報
```bash
# 使用 CLI 提交測試警報
python main.py submit-alert -t "Suspicious Activity" -d "Multiple failed login attempts" -s HIGH

# 或使用 API
curl -X POST http://localhost:8000/alerts \
  -H "Content-Type: application/json" \
  -d '{"title": "Test Alert", "severity": "HIGH", ...}'
```

### 查看系統狀態
```bash
python main.py status
```

### 執行攻擊模擬
```bash
python main.py simulate
```

## API 端點

- `GET /health` - 系統健康檢查
- `POST /alerts` - 提交新警報
- `GET /tasks/{task_id}` - 查詢任務狀態
- `POST /approvals/{request_id}` - 處理批准請求
- `GET /metrics` - 獲取系統指標

## 配置說明

### 代理配置
每個代理可獨立配置 LLM 提供者和模型：
- Manager Agent：使用快速、便宜的模型（如 Gemini Flash）
- Hunter Agent：使用中階模型進行檢索
- Executor Agent：使用最強大的模型（如 GPT-4o、Claude Opus）

### 安全設定
- `ENABLE_HUMAN_APPROVAL`：是否啟用人工批准（建議保持開啟）
- `AUTO_EXECUTE_LOW_RISK`：是否自動執行低風險操作

## 監控與維運

系統包含 Prometheus + Grafana 監控堆疊：
- Prometheus：http://localhost:9090
- Grafana：http://localhost:3000 (admin/admin)

## 架構優勢

1. **職責分離**：每個代理專注其核心能力
2. **可擴展性**：可根據負載獨立擴展各代理
3. **容錯性**：單一代理故障不影響整體系統
4. **靈活性**：可輕鬆更換或升級個別組件
5. **成本優化**：不同任務使用適合的模型

## 開發指南

### 新增動作類型
在 `src/services/action_executor.py` 中實現新的動作處理器。

### 自定義威脅分析
修改 `src/agents/hunter_agent.py` 中的分析邏輯。

### 擴展通知管道
在 `src/infrastructure/notifications.py` 中新增通知服務。

## 故障排除

### RabbitMQ 連接失敗
確認 Docker 容器正在運行：
```bash
docker ps | grep rabbitmq
```

### Neo4j 連接問題
檢查 Neo4j 是否正確啟動並可訪問：
```bash
curl http://localhost:7474
```

### LLM API 錯誤
確認 API keys 正確設置在 .env 文件中。

## 授權

本專案採用 MIT 授權條款。

## 貢獻指南

歡迎提交 Issue 和 Pull Request！

## 聯絡方式

如有問題請聯繫：[your-email@example.com]
