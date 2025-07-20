# AgenticRAG AI 代理服務容器映像檔
# 多階段構建 - 開發與生產環境優化版本
# 基於 Python 3.11 精簡版本，針對生產環境優化

# 構建參數
ARG BUILD_ENV=production
ARG PYTHON_VERSION=3.11
ARG USER=appuser

# 基礎映像檔
FROM python:${PYTHON_VERSION}-slim as base

# 設定環境變數
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 設定工作目錄
WORKDIR /app

# 複製 Python 依賴項定義檔案
COPY requirements.txt requirements.lock.txt ./

# 安裝 Python 依賴項（使用鎖定版本確保可重現性）
RUN pip install --no-cache-dir -r requirements.lock.txt

# 開發環境配置
FROM base as development
EXPOSE 8000
CMD ["uvicorn", "main_new:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]

# 生產環境配置
FROM base as production
# 創建非 root 用戶
RUN groupadd -r ${USER} && useradd -r -g ${USER} ${USER}

# 複製應用程式原始碼
COPY ./app .

# 設定檔案權限
RUN chown -R ${USER}:${USER} /app

# 切換到非 root 用戶
USER ${USER}

# 開放 FastAPI 應用程式預設的 8000 連接埠
EXPOSE 8000

# 健康檢查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 定義容器啟動命令
CMD ["uvicorn", "main_new:app", "--host", "0.0.0.0", "--port", "8000"]