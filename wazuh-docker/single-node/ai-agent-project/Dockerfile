# AgenticRAG AI 代理服務容器映像檔
# 基於 Python 3.11 精簡版本，針對生產環境優化

# 使用官方 Python 3.11 精簡版映像檔作為基礎
# 選擇 slim 版本以減少映像檔大小，提升部署效率
FROM python:3.11-slim

# 設定容器內的工作目錄
# 所有後續操作都將在此目錄執行
WORKDIR /app

# 複製 Python 依賴項定義檔案
# 先複製 requirements.txt 以利用 Docker 層級快取
COPY requirements.txt .

# 安裝 Python 依賴項
# 使用 --no-cache-dir 避免快取以減少映像檔大小
# 包含 LangChain、OpenSearch、FastAPI 等核心套件
RUN pip install --no-cache-dir -r requirements.txt

# 複製 AgenticRAG 應用程式原始碼
# 包含主程式、嵌入服務、驗證腳本等所有核心模組
COPY ./app .

# 開放 FastAPI 應用程式預設的 8000 連接埠
# 此連接埠用於健康檢查和 API 端點
EXPOSE 8000

# 定義容器啟動命令
# 使用 uvicorn ASGI 伺服器執行 FastAPI 應用程式
# 綁定到所有網路介面以允許外部存取
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]