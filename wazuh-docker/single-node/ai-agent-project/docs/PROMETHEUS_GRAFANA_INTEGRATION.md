# Wazuh AI Agent - Prometheus + Grafana 監控整合完成報告

## 🎯 專案概述

已成功為 Wazuh AI Agent 實施完整的 Prometheus + Grafana 監控解決方案，按照監控最佳實踐構建標準化的監控中間層，實現從應用程式指標收集到視覺化儀表板的端到端監控流程。

## 🏗️ 整體架構

```
AI Agent (暴露指標) -> Prometheus (抓取並儲存指標) -> Grafana (查詢 Prometheus 並視覺化)
```

## ✅ 已實施的功能

### 1. 應用程式指標儀表化

#### 📊 核心指標類型
- **延遲指標 (Latency)**
  - `alert_processing_duration_seconds`: 處理單個警報的總耗時 (Histogram)
  - `api_call_duration_seconds`: 各階段 API 呼叫的耗時，可透過標籤區分 (Histogram)
  - `retrieval_duration_seconds`: 資料檢索階段的耗時 (Histogram)

- **Token 指標 (Token Usage)**
  - `llm_input_tokens_total`: LLM 分析使用的總輸入 Token 數 (Counter)
  - `llm_output_tokens_total`: LLM 分析產生的總輸出 Token 數 (Counter)
  - `embedding_input_tokens_total`: Embedding 使用的總輸入 Token 數 (Counter)

- **吞吐量與隊列 (Throughput & Queue)**
  - `alerts_processed_total`: 已成功處理的警報總數 (Counter)
  - `new_alerts_found_total`: 每次輪詢發現的新警報數 (Counter)
  - `pending_alerts_gauge`: 待處理的警報數量 (Gauge)

- **錯誤率 (Error Rate)**
  - `alert_processing_errors_total`: 處理失敗的警報總數 (Counter)
  - `api_errors_total`: API 呼叫失敗計數，可透過標籤區分 (Counter)
  - `graph_retrieval_fallback_total`: 從圖形檢索降級到傳統檢索的次數 (Counter)

#### 🔧 具體實施位置
- **FastAPI 應用程式**: 在 `main.py` 中添加 `/metrics` 端點
- **核心處理函數**: 在 `process_single_alert` 函數中完整儀表化
- **API 調用監控**: 
  - Embedding API 調用 (Google Gemini)
  - LLM 分析調用 (Anthropic Claude / Google Gemini)
  - Neo4j 圖形查詢調用
- **錯誤處理**: 各階段的異常和回退機制監控

### 2. Prometheus 配置

#### 📝 配置文件
- `prometheus.yml`: 完整的 Prometheus 配置
  - 10 秒抓取間隔
  - AI Agent 目標配置
  - 適當的標籤和重標記

#### 🐳 Docker 容器化
- 使用 `prom/prometheus:v2.48.0` 官方映像
- 30 天指標保留期間
- 啟用管理 API 和生命周期管理

### 3. Grafana 儀表板

#### 📈 預配置儀表板
完整的 "Wazuh AI Agent - GraphRAG Monitoring Dashboard"，包含：

1. **Alert Processing Rate**: 警報處理速率趨勢
2. **Pending Alerts Queue**: 待處理警報隊列監控 (Gauge)
3. **Alert Processing Latency**: P50/P95/P99 延遲分析
4. **API Call Duration by Stage**: 各階段 API 調用耗時
5. **Data Retrieval Duration**: 資料檢索效能
6. **Token Usage Rate**: Token 消耗趨勢
7. **Error Rate**: 錯誤率監控（按階段分類）
8. **Graph Retrieval Fallback Rate**: GraphRAG 系統健康度

#### 🔧 自動配置
- Prometheus 資料源自動配置
- 儀表板自動載入
- 適當的刷新間隔 (5 秒)

### 4. 部署和操作工具

#### 📄 配置管理
- **Docker Compose**: `docker-compose.monitoring.yml`
- **資料源配置**: `grafana/provisioning/datasources/prometheus.yml`
- **儀表板配置**: `grafana/provisioning/dashboards/dashboard.yml`

#### 🚀 自動化腳本
- **`start-monitoring.sh`**: 一鍵啟動監控系統
  - 系統檢查
  - 服務健康檢查
  - 自動網路配置
  - 詳細的狀態報告

#### 📚 文檔
- **`MONITORING_SETUP.md`**: 完整的部署和使用指南
- **`PROMETHEUS_GRAFANA_INTEGRATION.md`**: 本報告

## 🎯 關鍵特性

### 1. 生產就緒配置
- 適當的指標保留策略
- 高效的資源使用
- 安全的預設設定

### 2. 全面的效能監控
- 端到端的處理時間追蹤
- 每個階段的詳細指標
- 回退和錯誤監控

### 3. 成本追蹤
- Token 使用量監控
- API 調用成本估算
- 使用趨勢分析

### 4. 可靠性監控
- 錯誤率追蹤
- 服務健康檢查
- 隊列積壓監控

## 📊 指標範例和使用案例

### 延遲分析
```promql
# P95 警報處理時間
histogram_quantile(0.95, rate(alert_processing_duration_seconds_bucket[5m]))

# 各階段 API 調用延遲
histogram_quantile(0.95, rate(api_call_duration_seconds_bucket[5m])) by (stage)
```

### 吞吐量監控
```promql
# 警報處理速率
rate(alerts_processed_total[5m])

# 新警報發現速率
rate(new_alerts_found_total[5m])
```

### 錯誤率分析
```promql
# 整體錯誤率
rate(alert_processing_errors_total[5m]) / rate(alerts_processed_total[5m])

# 各階段 API 錯誤率
rate(api_errors_total[5m]) by (stage)
```

### 成本監控
```promql
# 每小時 Token 消耗
increase(llm_input_tokens_total[1h])
increase(llm_output_tokens_total[1h])
increase(embedding_input_tokens_total[1h])
```

## 🔧 使用方式

### 快速啟動
```bash
cd wazuh-docker/single-node/ai-agent-project/
./start-monitoring.sh
```

### 訪問服務
- **AI Agent 指標**: http://localhost:8000/metrics
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000
  - 使用者名稱: `admin`
  - 密碼: `wazuh-grafana-2024`

### 手動管理
```bash
# 啟動監控服務
docker-compose -f docker-compose.monitoring.yml up -d

# 檢查服務狀態
docker-compose -f docker-compose.monitoring.yml ps

# 查看日誌
docker-compose -f docker-compose.monitoring.yml logs -f

# 停止監控服務
docker-compose -f docker-compose.monitoring.yml down
```

## 🚨 告警建議

建議在 Grafana 中設定以下告警規則：

1. **高錯誤率**: 錯誤率超過 5%
2. **高延遲**: P95 處理時間超過 10 秒
3. **隊列積壓**: 待處理警報超過 50 個
4. **服務不可用**: 超過 1 分鐘沒有新指標
5. **高回退率**: GraphRAG 回退率超過 20%

## 📈 未來擴展

### 可能的增強功能
1. **自定義告警規則**: 添加更細粒度的告警
2. **多環境支援**: 開發、測試、生產環境的分離
3. **成本最佳化**: 基於指標的自動成本最佳化建議
4. **效能基準**: 自動化效能基準測試和比較
5. **容量規劃**: 基於歷史資料的容量預測

### 整合建議
1. **日誌系統**: 與 ELK/EFK 堆疊整合
2. **追蹤系統**: 添加分散式追蹤 (Jaeger/Zipkin)
3. **告警管理**: 與 PagerDuty/Slack 整合
4. **自動化**: CI/CD 流程中的監控配置

## ✅ 驗證清單

- [x] prometheus-client 依賴已添加
- [x] FastAPI /metrics 端點已實施
- [x] 核心處理函數已完全儀表化
- [x] API 調用監控已實施 (Embedding, LLM, Neo4j)
- [x] 錯誤處理和回退監控已實施
- [x] Prometheus 配置已完成
- [x] Grafana 資料源配置已完成
- [x] 完整的監控儀表板已創建
- [x] Docker Compose 監控服務配置已完成
- [x] 自動化啟動腳本已創建
- [x] 完整的使用文檔已編寫

## 🎉 結論

Wazuh AI Agent 現在具備了生產級的監控能力，能夠：

1. **實時監控**: 所有關鍵指標的實時追蹤
2. **效能分析**: 詳細的延遲和吞吐量分析
3. **成本控制**: Token 使用和 API 調用成本監控
4. **可靠性保證**: 錯誤率和服務健康監控
5. **可視化儀表板**: 直觀的 Grafana 儀表板
6. **自動化部署**: 一鍵式監控系統部署

這套監控解決方案為 AI Agent 的運維和最佳化提供了堅實的基礎，有助於確保系統的穩定性、效能和成本效益。