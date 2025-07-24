#!/usr/bin/env python3
"""
最小化的 FastAPI 應用程式，用於測試 metrics 端點
"""

import os
import sys
from pathlib import Path

# 添加 app 目錄到 Python 路徑
sys.path.insert(0, str(Path(__file__).parent / "app"))

from fastapi import FastAPI, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram
import time

# 創建 Prometheus Registry
REGISTRY = CollectorRegistry()

# 定義一些指標
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status'],
    registry=REGISTRY
)

REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint'],
    registry=REGISTRY
)

# 創建 FastAPI 應用
app = FastAPI(
    title="Wazuh GraphRAG AI Agent - Minimal",
    version="1.0.0"
)

# 中間件來追踪請求
@app.middleware("http")
async def track_requests(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    # 記錄指標
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    
    REQUEST_LATENCY.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration)
    
    return response

@app.get("/")
async def read_root():
    """根端點"""
    return {
        "status": "AI Triage Agent is running",
        "stage": "development",
        "features": [
            "Prometheus monitoring",
            "GraphRAG analysis"
        ]
    }

@app.get("/health")
async def health_check():
    """健康檢查端點"""
    return {
        "status": "healthy",
        "checks": {
            "app": "ok"
        }
    }

@app.get("/metrics")
async def get_metrics():
    """Prometheus metrics 端點"""
    return Response(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST
    )

if __name__ == "__main__":
    import uvicorn
    print("啟動最小化 FastAPI 應用...")
    print("訪問 http://localhost:8000/ 查看狀態")
    print("訪問 http://localhost:8000/metrics 查看 Prometheus 指標")
    uvicorn.run(app, host="0.0.0.0", port=8000)