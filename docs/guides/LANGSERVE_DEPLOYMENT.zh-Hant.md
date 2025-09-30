# LangServe 部署指南

本指南涵蓋了如何啟動由 LangServe 驅動、包裝了 LangGraph 協調器的 API。

## 先決條件
- Python 3.10+
- `security-agent-system/requirements.txt` 中的依賴項
- 用於 LLM 供應商和基礎設施後端的有效環境變數

## 快速入門
1. 安裝依賴項：
   ```bash
   pip install -r security-agent-system/requirements.txt
   ```
2. 設定環境配置（請參閱 `.env.example`）。
3. 執行 LangServe 應用程式：
   ```bash
   uvicorn apps.langserve.app:app --host 0.0.0.0 --port 8001
   ```
4. 在 `http://localhost:8001/docs` 或 `http://localhost:8001/playground` 與 LangServe UI 互動。

## 端點
- `POST /alerts/invoke` – 提交安全警報負載並接收協調結果。
- `GET /health` – 平台健康檢查，包括協調器準備情況。
- `GET /runtime/status` – LangGraph 執行時元資料的快照。

## 擴展技巧
- 在反向代理（NGINX）後執行以進行 TLS 終止。
- 根據 CPU 核心數配置 Uvicorn 工作程序：`uvicorn ... --workers 2`。
- 根據每個部署階段，使用環境變數選擇代理和資料庫後端。

## 可觀察性
- FastAPI 日誌使用 Structlog 上下文進行了豐富。
- Prometheus 指標在 `/metrics` 下公開（請相應地掛載您的收集器）。
- 當配置完成後，LangServe 的執行追蹤會自動傳播到 LangSmith。