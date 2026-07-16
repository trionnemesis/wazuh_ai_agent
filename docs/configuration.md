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
