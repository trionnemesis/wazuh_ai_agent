[← 回到 README](../README.md)

# 進階配置與客製化

### LLM 模型切換
```bash
# 切換至 Google Gemini
echo "LLM_PROVIDER=gemini" >> ai-agent-project/.env
docker-compose restart ai-agent

# 切換至 Anthropic Claude
echo "LLM_PROVIDER=anthropic" >> ai-agent-project/.env
docker-compose restart ai-agent
```

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
