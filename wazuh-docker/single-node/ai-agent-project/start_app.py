#!/usr/bin/env python3
"""
主應用程式啟動腳本
"""

import os
import sys
from pathlib import Path

# 設置 Python 路徑
project_root = Path(__file__).parent
app_path = project_root / "app"
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(app_path))

# 設置必要的環境變數
os.environ.setdefault("APP_STAGE", "development")
os.environ.setdefault("APP_TITLE", "Wazuh GraphRAG AI Agent")
os.environ.setdefault("APP_VERSION", "3.0.0")

# 如果沒有 .env 文件，從 performance-optimization.env 複製
env_file = project_root / ".env"
if not env_file.exists():
    perf_env = project_root / "performance-optimization.env"
    if perf_env.exists():
        import shutil
        shutil.copy(perf_env, env_file)
        print(f"已複製 {perf_env} 到 {env_file}")

# 加載環境變數
from dotenv import load_dotenv
load_dotenv()

if __name__ == "__main__":
    try:
        print("正在啟動 Wazuh GraphRAG AI Agent...")
        print(f"Python 路徑: {sys.path}")
        print(f"工作目錄: {os.getcwd()}")
        
        # 導入並運行應用程式
        from main_new import app
        import uvicorn
        
        uvicorn.run(
            app, 
            host="0.0.0.0", 
            port=8000,
            log_level="info",
            reload=False
        )
    except Exception as e:
        print(f"啟動錯誤: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)