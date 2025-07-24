# Metrics 端點修復指南

## 問題描述

原始問題：訪問 `http://localhost:8000/metrics` 時返回 `{"detail":"Not Found"}`

## 問題原因

1. **相對導入問題**：Python 模組之間的相對導入路徑不正確
2. **Python 路徑配置**：應用程式啟動時未正確設置 Python 路徑
3. **環境變數缺失**：某些必要的環境變數未設置

## 解決方案

### 1. 修復導入路徑

在 `app/api/endpoints.py` 中，將相對導入改為絕對導入：

```python
# 原來的（錯誤）
from ..core.config import get_config_summary, APP_STAGE
from ..core.scheduler import get_scheduler_status
from ..api.health_check import perform_health_check
from ..services.metrics import REGISTRY
from ..utils.cache_manager import get_cache_service

# 修改後（正確）
from core.config import get_config_summary, APP_STAGE
from core.scheduler import get_scheduler_status
from api.health_check import perform_health_check
from services.metrics import REGISTRY
from utils.cache_manager import get_cache_service
```

在 `app/core/scheduler.py` 中也需要類似修改：

```python
# 原來的（錯誤）
from ..services.alert_service import triage_new_alerts

# 修改後（正確）
from services.alert_service import triage_new_alerts
```

### 2. 創建啟動腳本

創建 `start_app.py` 來正確設置 Python 路徑和環境變數：

```python
#!/usr/bin/env python3
import os
import sys
from pathlib import Path

# 設置 Python 路徑
project_root = Path(__file__).parent
app_path = project_root / "app"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(app_path))

# 設置環境變數
os.environ.setdefault("APP_STAGE", "development")
os.environ.setdefault("APP_TITLE", "Wazuh GraphRAG AI Agent")
os.environ.setdefault("APP_VERSION", "3.0.0")

# 加載 .env 文件
from dotenv import load_dotenv
load_dotenv()

# 啟動應用
from app.main_new import app
import uvicorn
uvicorn.run(app, host="0.0.0.0", port=8000)
```

### 3. 最小化測試應用

為了驗證 metrics 功能，創建了 `minimal_app.py`：

```python
from fastapi import FastAPI, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, CollectorRegistry

REGISTRY = CollectorRegistry()
app = FastAPI()

@app.get("/metrics")
async def get_metrics():
    return Response(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST
    )
```

## 使用方法

### 1. 安裝依賴

```bash
pip install --break-system-packages -r requirements.txt
```

### 2. 設置環境變數

```bash
cp performance-optimization.env .env
```

### 3. 啟動應用程式

**使用啟動腳本：**
```bash
python3 start_app.py
```

**或使用 nohup 在後台運行：**
```bash
nohup python3 start_app.py > app.log 2>&1 &
```

**或使用最小化測試應用：**
```bash
python3 minimal_app.py
```

### 4. 訪問端點

- 根端點：`http://localhost:8000/`
- 健康檢查：`http://localhost:8000/health`
- Prometheus 指標：`http://localhost:8000/metrics`
- 快取統計：`http://localhost:8000/cache/stats`

## 驗證 Metrics

訪問 metrics 端點應該返回 Prometheus 格式的指標：

```bash
curl http://localhost:8000/metrics
```

預期輸出範例：
```
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{endpoint="/",method="GET",status="200"} 1.0
# HELP http_request_duration_seconds HTTP request latency
# TYPE http_request_duration_seconds histogram
...
```

## 可用的指標

主應用程式提供以下 Prometheus 指標：

1. **HTTP 請求指標**
   - `http_requests_total`: 總請求數（按方法、端點、狀態碼分組）
   - `http_request_duration_seconds`: 請求延遲直方圖

2. **警報處理指標**
   - `alerts_processed_total`: 處理的警報總數
   - `alert_processing_duration_seconds`: 警報處理時間
   - `alert_processing_errors_total`: 處理錯誤數

3. **GraphRAG 指標**
   - `graphrag_queries_total`: GraphRAG 查詢總數
   - `graphrag_query_duration_seconds`: 查詢執行時間
   - `graphrag_cache_hits_total`: 快取命中數
   - `graphrag_cache_misses_total`: 快取未命中數

4. **嵌入服務指標**
   - `embeddings_generated_total`: 生成的嵌入總數
   - `embedding_generation_duration_seconds`: 嵌入生成時間
   - `embedding_cache_size`: 當前快取大小

## 故障排除

1. **連接被拒絕錯誤**
   - 確認應用程式正在運行：`ps aux | grep python`
   - 檢查日誌文件：`cat app.log`

2. **模組未找到錯誤**
   - 確保使用正確的啟動腳本
   - 驗證 Python 路徑設置正確

3. **環境變數問題**
   - 確認 `.env` 文件存在
   - 檢查必要的環境變數是否設置

## 總結

通過修復導入路徑問題和創建適當的啟動腳本，成功解決了 metrics 端點的 404 錯誤。現在應用程式可以正常暴露 Prometheus 指標，支援監控和性能分析。