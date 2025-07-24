#!/usr/bin/env python3
"""
測試 FastAPI 應用程式和 metrics 端點的腳本
"""

import os
import sys
from pathlib import Path

# 將 app 目錄加入 Python 路徑
app_path = Path(__file__).parent / "app"
sys.path.insert(0, str(app_path))

# 設置基本的環境變數
os.environ.setdefault("APP_STAGE", "development")
os.environ.setdefault("OPENSEARCH_HOST", "localhost")
os.environ.setdefault("OPENSEARCH_PORT", "9200")
os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")
os.environ.setdefault("NEO4J_USER", "neo4j")
os.environ.setdefault("NEO4J_PASSWORD", "password")
os.environ.setdefault("CACHE_ENABLED", "true")

if __name__ == "__main__":
    try:
        print("正在啟動 FastAPI 應用程式...")
        from main_new import app
        import uvicorn
        
        # 啟動應用程式
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
    except Exception as e:
        print(f"錯誤: {e}")
        import traceback
        traceback.print_exc()