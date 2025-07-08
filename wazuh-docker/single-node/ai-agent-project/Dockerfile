# 使用官方的 Python 映像檔
FROM python:3.11-slim

# 設定工作目錄
WORKDIR /app

# 複製依賴項檔案
COPY requirements.txt .

# 安裝依賴項
RUN pip install --no-cache-dir -r requirements.txt

# 複製應用程式程式碼
COPY ./app .

# 開放 FastAPI 預設的 8000 連接埠
EXPOSE 8000

# 執行應用程式的命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]