# Wazuh AI Agent 監控系統部署指南

本指南說明如何為 Wazuh AI Agent 部署 Prometheus + Grafana 監控解決方案。

## 🏗️ 監控架構

```
AI Agent (暴露指標) -> Prometheus (抓取並儲存指標) -> Grafana (查詢 Prometheus 並視覺化)
```

## 📊 監控的關鍵指標 (KPIs)

### 延遲指標 (Latency)
- `alert_processing_duration_seconds`: 處理單個警報的總耗時 (Histogram)
- `api_call_duration_seconds`: 各階段 API 呼叫的耗時，可透過標籤區分 (Histogram)
- `retrieval_duration_seconds`: 資料檢索階段的耗時 (Histogram)

### Token 指標 (Token Usage)
- `llm_input_tokens_total`: LLM 分析使用的總輸入 Token 數 (Counter)
- `llm_output_tokens_total`: LLM 分析產生的總輸出 Token 數 (Counter)
- `embedding_input_tokens_total`: Embedding 使用的總輸入 Token 數 (Counter)

### 吞吐量與隊列 (Throughput & Queue)
- `alerts_processed_total`: 已成功處理的警報總數 (Counter)
- `new_alerts_found_total`: 每次輪詢發現的新警報數 (Counter)
- `pending_alerts_gauge`: 待處理的警報數量 (Gauge)

### 錯誤率 (Error Rate)
- `alert_processing_errors_total`: 處理失敗的警報總數 (Counter)
- `api_errors_total`: API 呼叫失敗計數，可透過標籤區分 (Counter)
- `graph_retrieval_fallback_total`: 從圖形檢索降級到傳統檢索的次數 (Counter)

## 🚀 部署步驟

### 1. 安裝依賴

確保 AI Agent 的 `requirements.txt` 包含 `prometheus-client`：

```bash
pip install prometheus-client
```

### 2. 啟動監控服務

使用 Docker Compose 啟動 Prometheus 和 Grafana：

```bash
# 在 ai-agent-project 目錄中
docker-compose -f docker-compose.monitoring.yml up -d
```

### 3. 驗證服務狀態

檢查所有服務是否正常運行：

```bash
docker-compose -f docker-compose.monitoring.yml ps
```

### 4. 訪問服務

- **AI Agent 指標端點**: http://localhost:8000/metrics
- **Prometheus UI**: http://localhost:9090
- **Grafana Dashboard**: http://localhost:3000

## 🔐 預設登入資訊

### Grafana
- **使用者名稱**: admin
- **密碼**: wazuh-grafana-2024

## 📈 使用 Grafana 儀表板

### 1. 登入 Grafana
訪問 http://localhost:3000 並使用上述憑證登入。

### 2. 導入儀表板
儀表板會自動配置，或者您可以：
1. 點擊左側選單的 "Dashboards"
2. 選擇 "Browse" 
3. 查找 "Wazuh AI Agent - GraphRAG Monitoring Dashboard"

### 3. 關鍵視圖說明

#### Alert Processing Rate
- 顯示警報處理速率和新警報發現速率
- 用於監控系統吞吐量

#### Pending Alerts Queue
- 顯示當前待處理的警報數量
- 用於監控系統負載和積壓情況

#### Alert Processing Latency
- P50/P95/P99 延遲圖表
- 用於監控處理效能和識別效能瓶頸

#### API Call Duration by Stage
- 各階段（embedding、LLM 分析、Neo4j）的 API 呼叫耗時
- 用於識別最慢的處理階段

#### Token Usage Rate
- LLM 和 Embedding 的 Token 消耗趨勢
- 用於監控和預測 API 成本

#### Error Rate
- 錯誤率儀表盤，按階段分類
- 用於監控系統可靠性

#### Graph Retrieval Fallback Rate
- 從圖形檢索降級到傳統檢索的頻率
- 用於監控 GraphRAG 系統的健康狀況

## 🔧 自定義配置

### Prometheus 配置
編輯 `prometheus.yml` 來調整抓取間隔或添加新的目標：

```yaml
scrape_configs:
  - job_name: 'ai-agent'
    static_configs:
      - targets: ['ai-agent:8000']
    scrape_interval: 10s  # 調整抓取間隔
```

### Grafana 儀表板
您可以：
1. 在 Grafana UI 中編輯現有儀表板
2. 添加新的圖表和面板
3. 設定告警規則

## 📊 PromQL 查詢範例

### 警報處理速率
```promql
rate(alerts_processed_total[5m])
```

### P95 處理延遲
```promql
histogram_quantile(0.95, rate(alert_processing_duration_seconds_bucket[5m]))
```

### 錯誤率
```promql
rate(alert_processing_errors_total[5m]) / rate(alerts_processed_total[5m])
```

### Token 使用趨勢
```promql
increase(llm_input_tokens_total[1h])
```

## 🚨 告警設定

### 建議的告警規則

1. **高錯誤率**: 錯誤率超過 5%
2. **高延遲**: P95 處理時間超過 10 秒
3. **隊列積壓**: 待處理警報超過 50 個
4. **服務不可用**: 超過 1 分鐘沒有新指標

### 配置告警
1. 在 Grafana 中設定告警規則
2. 配置通知渠道（Email、Slack 等）
3. 設定告警條件和閾值

## 🛠️ 故障排除

### 常見問題

1. **指標端點無法訪問**
   - 檢查 AI Agent 是否正在運行
   - 確認 `/metrics` 端點返回 200 狀態

2. **Prometheus 無法抓取指標**
   - 檢查網路連接
   - 驗證服務發現配置

3. **Grafana 無法連接 Prometheus**
   - 確認 Prometheus 服務正在運行
   - 檢查數據源配置

### 日誌檢查
```bash
# 檢查 Prometheus 日誌
docker logs wazuh-prometheus

# 檢查 Grafana 日誌
docker logs wazuh-grafana

# 檢查 AI Agent 日誌
docker logs wazuh-ai-agent
```

## 🔄 維護和更新

### 定期任務
1. 清理舊的指標數據（Prometheus 預設保留 30 天）
2. 備份 Grafana 儀表板配置
3. 監控存儲使用量
4. 更新告警規則

### 效能調優
1. 根據需求調整 Prometheus 抓取間隔
2. 優化 Grafana 查詢以減少負載
3. 設定適當的指標保留期間

## 📚 相關文檔

- [Prometheus 官方文檔](https://prometheus.io/docs/)
- [Grafana 官方文檔](https://grafana.com/docs/)
- [prometheus-client Python 文檔](https://prometheus.github.io/client_python/)

## 🤝 支援

如有問題或建議，請聯繫 AI Agent 開發團隊。