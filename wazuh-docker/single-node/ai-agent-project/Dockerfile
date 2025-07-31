# AgenticRAG AI 代理服務容器映像檔
# 多階段構建 - 開發與生產環境優化版本
# 基於 Python 3.11 精簡版本，針對生產環境優化

# 構建參數
ARG BUILD_ENV=production
ARG PYTHON_VERSION=3.11
ARG USER=appuser
ARG GROUP=appgroup

# ==============================================================================
# 1. 基礎映像檔 (base)
# 包含所有共享的依賴、設定和非 root 使用者
# ==============================================================================
FROM python:${PYTHON_VERSION}-slim as base

# 設定環境變數 (保持不變)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 安裝系統依賴 (保持不變)
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 創建非 root 使用者和群組 (保持不變)
RUN if ! getent group ${GROUP} > /dev/null; then groupadd -r ${GROUP}; fi && \
    if ! getent passwd ${USER} > /dev/null; then useradd -r -g ${GROUP} -s /bin/false ${USER}; fi

# 設定工作目錄
WORKDIR /app

# 複製 Python 依賴項定義檔案
COPY requirements.txt requirements.lock.txt ./

# 安裝 Python 依賴項
RUN pip install --no-cache-dir -r requirements.txt

# --- ✨ 修正點 1: 簡化程式碼複製 ---
# 將本地的 `./app` 目錄下的 *內容* 直接複製到工作目錄 `/app`
# 這樣，`main_new.py` 和 `core/` 目錄會直接位於 `/app` 下
# 而不是之前的 `/app/app`
COPY ./app .

# --- ✨ 修正點 2: 移除不必要的 PYTHONPATH ---
# 因為現在的目錄結構是扁平的 (`/app/main_new.py`, `/app/core/`)
# Python 會自動將工作目錄 `/app` 加入搜索路徑，所以不再需要手動設定 PYTHONPATH
# ENV PYTHONPATH=/app/app # <- 已移除

# ==============================================================================
# 2. 開發環境 (development)
# ==============================================================================
FROM base as development

# 複製整個專案目錄以包含開發工具的設定檔 (例如 .vscode, pyproject.toml 等)
COPY . /app

# 將工作目錄的所有權交給 appuser，以便在 reload 模式下寫入 pycache 等檔案
RUN chown -R ${USER}:${GROUP} /app

# 切換到非 root 使用者
USER ${USER}

# 開放連接埠
EXPOSE 8000

# --- ✨ 修正點 3: 統一並簡化啟動命令 ---
# 由於 `main_new.py` 現在位於工作目錄的頂層，可以直接引用
CMD ["uvicorn", "main_new:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]

# ==============================================================================
# 3. 生產環境 (production)
# ==============================================================================
FROM base as production

# 在 base 階段，我們已經複製了應用程式碼。
# 為了保持映像檔乾淨，生產環境不再需要從本地複製整個專案 (`COPY . /app`)
# base 階段的程式碼已經足夠。
# 如果有靜態檔案或其他需要從專案根目錄複製的資源，可以在這裡單獨添加 COPY 指令。
# 例如：COPY --chown=${USER}:${GROUP} ./static /app/static

# 將工作目錄的所有權交給 appuser
RUN chown -R ${USER}:${GROUP} /app

# 切換到非 root 使用者
USER ${USER}

# 開放連接埠
EXPOSE 8000

# 健康檢查 (路徑正確，保持不變)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# --- ✨ 修正點 4: 修正生產環境的啟動命令 ---
# 使用 main.py 作為入口點（它會導入 main_new.py）
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
