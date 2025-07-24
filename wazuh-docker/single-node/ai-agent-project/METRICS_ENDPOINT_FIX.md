# Prometheus Metrics 端點修復說明

## 問題描述
訪問 `http://localhost:8000/metrics` 時返回 `{"detail":"Not Found"}` 錯誤。

## 根本原因
1. 主應用程式 `main.py` 中沒有定義 `/metrics` 端點
2. 提供的 `endpoints.py` 檔案沒有被整合到主應用程式中
3. 缺少 `prometheus-client` 依賴項

## 解決方案

### 1. 添加 Prometheus 客戶端依賴
在 `requirements.txt` 中添加：
```
prometheus-client # Prometheus 監控指標客戶端
```

### 2. 在 main.py 中添加 Prometheus 支援

#### 導入必要的模組
```python
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST, REGISTRY
from fastapi import Response
```

#### 定義 Prometheus 指標
```python
# 計數器指標
alerts_processed_total = Counter(
    'wazuh_alerts_processed_total',
    'Total number of Wazuh alerts processed',
    ['status']
)

alerts_vectorized_total = Counter(
    'wazuh_alerts_vectorized_total',
    'Total number of alerts vectorized'
)

ai_analysis_total = Counter(
    'wazuh_ai_analysis_total',
    'Total number of AI analyses performed',
    ['severity', 'decision']
)

# 直方圖指標
processing_duration = Histogram(
    'wazuh_alert_processing_duration_seconds',
    'Time spent processing alerts',
    ['operation']
)

embedding_duration = Histogram(
    'wazuh_embedding_generation_duration_seconds',
    'Time spent generating embeddings'
)

# 測量指標
active_alerts = Gauge(
    'wazuh_active_alerts',
    'Number of active alerts in the system'
)

system_health = Gauge(
    'wazuh_system_health',
    'System health status (1=healthy, 0=unhealthy)'
)
```

#### 添加 /metrics 端點
```python
@app.get("/metrics")
async def get_metrics():
    """Prometheus 指標端點"""
    # 更新系統健康狀態指標
    try:
        health = await health_check()
        system_health.set(1 if health.get("status") == "healthy" else 0)
        
        # 更新活躍警報數量
        if "processing_stats" in health:
            active_alerts.set(health["processing_stats"].get("total_alerts", 0))
    except Exception as e:
        logger.error(f"更新指標時發生錯誤: {str(e)}")
        system_health.set(0)
    
    # 生成並返回 Prometheus 格式的指標
    return Response(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST
    )
```

### 3. 在處理邏輯中更新指標

#### 處理警報時更新指標
```python
# 成功處理
alerts_processed_total.labels(status='success').inc()

# 失敗處理
alerts_processed_total.labels(status='failed').inc()
```

#### 生成嵌入時更新指標
```python
with embedding_duration.time():
    alert_vector = await embedding_service.embed_alert_content(alert_source)
alerts_vectorized_total.inc()
```

#### AI 分析完成時更新指標
```python
severity = risk_level.lower() if risk_level != "Unknown" else "unknown"
decision = "escalate" if risk_level in ['Critical', 'High'] else "monitor"
ai_analysis_total.labels(severity=severity, decision=decision).inc()
```

## 測試驗證

創建了 `test_metrics_endpoint.py` 測試腳本，驗證結果顯示：

1. `/metrics` 端點正常返回 Prometheus 格式的指標
2. 所有自定義指標都正確暴露：
   - `wazuh_alerts_processed_total{status="success|failed"}`
   - `wazuh_alerts_vectorized_total`
   - `wazuh_ai_analysis_total{severity="...", decision="..."}`
   - `wazuh_active_alerts`
   - `wazuh_system_health`
   - `wazuh_alert_processing_duration_seconds`
   - `wazuh_embedding_generation_duration_seconds`

## 部署注意事項

1. 確保 Docker 映像重新構建以包含 `prometheus-client` 依賴項
2. 如果使用 Docker Compose，需要重新構建容器：
   ```bash
   docker-compose build ai-agent
   docker-compose up -d ai-agent
   ```

3. 驗證端點：
   ```bash
   curl http://localhost:8000/metrics
   ```

## 監控整合

這些指標可以被 Prometheus 收集，並在 Grafana 中視覺化，以監控：
- 警報處理成功率
- 向量化效能
- AI 分析分佈
- 系統健康狀態
- 處理時間分佈