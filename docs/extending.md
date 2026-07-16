[← 回到 README](../README.md)

# 擴充開發指南

### 1. 新增 LLM 供應商
在 `get_llm()` 函式中新增支援：
```python
elif LLM_PROVIDER == 'openai':
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model="gpt-4", openai_api_key=OPENAI_API_KEY)
```

### 2. 客製化分析邏輯
建立專用的分析函式：
```python
async def analyze_specific_rule_type(alert_source):
    """針對特定規則類型的客製化分析"""
    rule_id = alert_source.get('rule', {}).get('id')
    if rule_id == '5710':  # SSH 登入失敗
        # 特殊處理邏輯
        pass
```

### 3. 整合外部威脅情報
```python
async def enrich_with_threat_intel(alert_source):
    """整合外部威脅情報"""
    source_ip = alert_source.get('srcip')
    # 查詢威脅情報資料庫
    threat_info = await query_threat_db(source_ip)
    return threat_info
```
