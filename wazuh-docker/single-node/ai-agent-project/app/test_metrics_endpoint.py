#!/usr/bin/env python3
"""
測試 Prometheus metrics 端點的實現
"""

import os
import sys
from fastapi import FastAPI, Response
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST, REGISTRY
import uvicorn

# 創建測試應用程式
app = FastAPI(title="Metrics Endpoint Test")

# === Prometheus 指標定義 ===
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

@app.get("/")
def read_root():
    """根端點"""
    return {"status": "Metrics test server is running"}

@app.get("/metrics")
async def get_metrics():
    """
    Prometheus 指標端點
    """
    # 模擬一些指標資料
    alerts_processed_total.labels(status='success').inc()
    alerts_processed_total.labels(status='failed').inc()
    alerts_vectorized_total.inc()
    ai_analysis_total.labels(severity='high', decision='escalate').inc()
    active_alerts.set(42)
    system_health.set(1)
    
    # 生成並返回 Prometheus 格式的指標
    return Response(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST
    )

@app.get("/test-metrics")
def test_metrics():
    """測試端點 - 增加一些指標值"""
    # 增加一些測試指標
    alerts_processed_total.labels(status='success').inc()
    alerts_vectorized_total.inc()
    with processing_duration.labels(operation='test').time():
        import time
        time.sleep(0.1)
    
    return {"message": "Metrics updated", "check": "/metrics endpoint to see the changes"}

if __name__ == "__main__":
    print("🚀 Starting metrics test server on http://localhost:8001")
    print("📊 Access metrics at: http://localhost:8001/metrics")
    print("🧪 Test metrics generation at: http://localhost:8001/test-metrics")
    uvicorn.run(app, host="0.0.0.0", port=8001)