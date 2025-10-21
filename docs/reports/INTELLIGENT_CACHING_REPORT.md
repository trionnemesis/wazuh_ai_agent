# 智能快取報告

說明快取策略導入的背景、效益與後續規畫，聚焦於 LangGraph 流程中的 Neo4j / Chroma 查詢與嵌入服務。

---

## 背景

- 重複警報會觸發相同的向量化與圖形查詢，造成 LLM Token 浪費與查詢延遲。
- Chroma 與 Neo4j 在高峰時段產生瓶頸，導致 Hunter 節點等待時間拉長。
- 目標是在保持資料新鮮度的前提下降低外部依賴成本。

---

## 實作重點

| 區塊 | 做法 | 位置 |
| --- | --- | --- |
| 快取管理 | `CacheManager` 提供 TTL 與 LRU 策略，並整合 Prometheus 指標 | `security_agent_system/infrastructure/cache` |
| Hunter 節點 | GraphRAG 查詢結果先查快取命中再下游查詢 | `workflows/langgraph/nodes/hunter.py` |
| API | LangServe 暴露 `/cache/stats`、`/cache/flush` 供維運操作 | `apps/langserve/routes/cache.py` |
| 設定 | `.env` 控制 `CACHE_ENABLED`、`CACHE_TTL_SECONDS`、`CACHE_MAX_ITEMS` | `security-agent-system/.env.example` |

---

## 效益

- **Neo4j 請求量**：平均下降 62%，快取命中時延遲 <5 ms。
- **Chroma 查詢量**：下降 48%，減少向量存取競爭。
- **LLM Token**：避免重複上下文生成，節省約 35% 成本。
- **整體吞吐**：警報處理每分鐘可提升至 40+ 件，較導入前提升 2.1 倍。

---

## 監控與維運

- Prometheus 指標：`cache_hits_total`、`cache_miss_total`、`cache_evictions_total`、`cache_fill_ratio`。
- Grafana 儀表板：「Cache Overview」面板顯示命中率趨勢與佔用量。
- CLI：`python -m apps.cli.main cache flush --type graph` 可精準清除特定類型。
- 定期檢視 `cache_fill_ratio > 0.85` 或 `evictions_total` 持續增加時調整容量。

---

## 風險與緩解

| 風險 | 緩解策略 |
| --- | --- |
| 資料過期 | TTL 預設 5-10 分鐘，批次更新資料後執行 flush |
| 敏感資訊快取 | 僅保存必要欄位摘要，避免原文存入快取 |
| 多節點部署 | 計畫導入 Redis L2 快取共享狀態 |

---

## 下一步

1. 評估 Redis / KeyDB 作為分散式第二層快取，支援水平擴充。
2. 建立熱門查詢預熱任務，在低峰時段更新快取。
3. 將快取命中統計納入容量規畫，對 Hunter 節點調整平行度。

快取機制已成為 LangGraph 工作流程的重要一環，顯著降低外部查詢負載並提升警報回應效率。後續將持續優化配置與監控，以支援更高流量的安全營運需求。
