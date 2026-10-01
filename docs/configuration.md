[← 回到 README](../README.md)

# 進階配置與客製化

### 環境變數與容器更新

以下指令在 `wazuh-docker/single-node/` 執行。Compose 從
`ai-agent-project/.env` 注入 Agent 的環境變數；這不是 single-node 目錄下的 `.env`。
在該檔案修改既有的 `LLM_PROVIDER` 與對應金鑰，不重複追加同名變數。
目前 factory 的模型名稱仍為硬編碼，provider/model 更新另由 [#68](https://github.com/trionnemesis/wazuh_ai_agent/issues/68) 追蹤。

```bash
# 只驗證設定，不啟動容器，也不輸出展開後的金鑰
docker compose config --quiet
# 更新 env_file 後須重建 Agent；restart 不會重新載入環境變數
docker compose up -d --no-deps --force-recreate ai-agent
```

### 完整 lab 的網路與存取

預設網路由 Compose 依專案名稱建立；在此目錄未指定專案名稱時為
`single-node_default`，不再要求外部網路事先存在。這是完整 stack 的入口，
仍依賴同一 Compose project 的 `wazuh.indexer`；不是既有 Wazuh 的 standalone 部署。
如果已有手動管理的 external network／容器，先核對現有 project 的網路與資料卷，
不要用刪除網路或 `down -v` 當作遷移步驟。
Agent 僅發布 `127.0.0.1:8000:8000`；Dockerfile 的 EXPOSE 本身不會發布 host port。

### 離線設定驗收

從 repository root 執行（Python 3 與 Docker Compose；不需 Docker daemon）：

```bash
python3 -m unittest discover -s tests -v
```

測試在暫存目錄解析 README 的假金鑰範例，執行真正的 `compose config --format json`，
驗證 env_file、build context、專案管理網路、loopback port 與原 Wazuh services／volumes 保留。
不讀取開發者的 `.env`、不 pull/build/start images、不呼叫 LLM／Indexer。
可透過 `COMPOSE_COMMAND=/path/to/docker-compose` 使用 standalone Compose executable。
這只證明設定可解析，不代表容器健康、模型可用或一筆 triage 已完成。

### 自訂分析排程
編輯 `ai-agent-project/app/main.py`：
```python
# 修改分析頻率 (預設 60 秒)
scheduler.add_job(triage_new_alerts, 'interval', seconds=30)  # 改為 30 秒
```

### RAG / Agent 決策迴圈 / 通知 調校
可在 `.env` 中調整以下進階參數（皆有預設值，非必填）：

```bash
EMBEDDING_MODEL=all-MiniLM-L6-v2   # sentence-transformers 模型，可換成其他語系模型
CONTEXT_LOOKBACK_HOURS=1           # 同主機 RAG 上下文的查詢時間窗
CONTEXT_TOP_K=3                    # RAG 相似度排序後取幾筆當上下文
BROADENED_LOOKBACK_HOURS=24        # agent 決策「需要更多上下文」時的擴大查詢時間窗
AI_AGENT_WEBHOOK_URL=              # 高風險 (Critical/High) 通知 webhook，留空則不通知
```

若要停用「agent 決策迴圈」、每次都直接用窄範圍上下文分析，可將 `decision_prompt_template` 的判斷邏輯拿掉，
或直接在 `triage_new_alerts()` 中略過 `decision_chain.ainvoke(...)` 這段，固定使用 `fetch_recent_host_context()` 的結果。

### 自訂提示模板
編輯分析提示以符合組織需求：
```python
prompt_template = ChatPromptTemplate.from_template(
    """您是資深資安分析師。請針對以下 Wazuh 警報進行專業分析...

    {alert_summary}
    {context}

    請提供：
    1. 事件摘要
    2. 風險等級評估
    3. 建議處置動作
    """
)
```
