# Docker 最佳化指南

本文整理在容器化部署 `security-agent-system` 時的資源優化與維運建議。

---

## 啟動流程精簡

- 使用 `docker-compose.main.yml` 作為單一入口，啟動腳本僅負責呼叫 `docker compose up` 與基本檢查。
- 健康檢查交由 Compose 定義：
  ```yaml
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
    interval: 30s
    timeout: 10s
    retries: 3
  ```
- 將初始化作業（建立索引、匯入圖資料）包裝成一次性 Job，避免啟動腳本內嵌大量邏輯。

---

## 設定管理

- `.env` 為唯一來源，範例內容維護於 `.env.example`。
- 建議以功能分區：
  ```env
  # === LangGraph ===
  DEFAULT_LLM_PROVIDER=anthropic
  MANAGER_LLM_PROVIDER=openai

  # === Neo4j ===
  NEO4J_URI=bolt://neo4j:7687
  NEO4J_AUTH=neo4j/test-password

  # === 監控 ===
  PROMETHEUS_SCRAPE_PORT=8001
  ```
- Compose 中避免重複宣告環境變數，改以 `${VAR}` 引用。

---

## 映像構建

1. 以多階段 Dockerfile 構建：
   - `builder`：安裝相依、執行測試。
   - `runtime`：僅複製必要模組與啟動腳本。
2. 將 `pip install` 改用 `pip install --no-cache-dir -r requirements.txt`，並善用 `pip wheel` 快取。
3. 基底映像建議使用 `python:3.11-slim` 搭配 `poetry export` 或 `pip-tools` 鎖定版本。

---

## 資源與安全

| 項目 | 建議 |
| --- | --- |
| CPU / RAM | `deploy.resources.limits` 針對 `ai-agent` 限制 4 vCPU、6 GB；Neo4j 依資料量調整 | 
| 儲存 | 採用具備持久化的 volume：`neo4j-data`、`chroma-data`、`logs` |
| 使用者 | 容器內新增非 root 帳號並切換為預設使用者 |
| 網路 | 自訂 `bridge` 網路並限制只暴露必要埠 |
| 日誌 | 啟用 `json-file` 旋轉：`max-size: 10m`、`max-file: 5` |

---

## 效能監控

- 以 `docker stats` 監控即時資源，Prometheus 收集 `container_cpu_usage_seconds_total` 等指標。
- 針對 Neo4j，設定 `dbms.memory.heap.max_size` 與 `pagecache.size`，並監控 `neo4j_page_cache_hit_ratio`。
- LangGraph 延遲可由 `/metrics` 直方圖推算，必要時提高 `UVICORN_TIMEOUT` 或增加 worker。

---

## 常見問題

| 問題 | 原因 | 解決方案 |
| --- | --- | --- |
| 容器啟動反覆重啟 | 健康檢查無法通過 | `docker compose logs <service>`，檢查依賴服務是否就緒 |
| `.env` 未載入 | 執行目錄錯誤或權限不足 | 確保在 Compose 目錄執行並檢查檔案權限 |
| 映像過大 | 未清理快取或保留測試依賴 | 使用多階段構建並刪除 `__pycache__`、臨時檔 |
| Neo4j I/O 打滿 | 預設記憶體不足 | 提升 `dbms.memory.heap.max_size`，並將圖資料移至 SSD |

---

依照本指南調整後，可在確保可觀測性的同時降低資源消耗並提升部署穩定度。
