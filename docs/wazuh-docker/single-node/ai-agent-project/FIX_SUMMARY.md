# 修正 "Timeout context manager should be used inside a task" 錯誤

## 問題描述
當執行 `triage_new_alerts()` 時出現以下錯誤：
```
RuntimeError: Timeout context manager should be used inside a task
```

這是因為 aiohttp 的 timeout context manager 需要在異步任務內使用，但是程式碼在同步上下文中創建了 AsyncOpenSearch 客戶端。

## 解決方案

### 1. 修改 `core/scheduler.py`
- 添加了 `async_job_wrapper()` 異步包裝函數
- 修改 `get_scheduler()` 使用當前的事件循環
- 將排程器任務改為使用異步包裝器而非直接調用異步函數

**主要變更：**
```python
# 新增異步包裝器
async def async_job_wrapper():
    """異步任務包裝器"""
    from services.alert_service import triage_new_alerts
    
    try:
        await triage_new_alerts()
    except Exception as e:
        logger.error(f"執行 triage_new_alerts 時發生錯誤: {str(e)}", exc_info=True)

# 修改排程器初始化
def get_scheduler() -> AsyncIOScheduler:
    global scheduler
    if scheduler is None:
        try:
            loop = asyncio.get_running_loop()
            scheduler = AsyncIOScheduler(event_loop=loop)
        except RuntimeError:
            scheduler = AsyncIOScheduler()
    return scheduler
```

### 2. 修改 `services/opensearch_service.py`
- 將 `get_opensearch_client()` 改為異步函數
- 確保客戶端在異步上下文中創建

**主要變更：**
```python
# 從同步函數改為異步函數
async def get_opensearch_client() -> AsyncOpenSearch:
    """獲取 OpenSearch 客戶端實例（單例模式）"""
    # ... 客戶端初始化代碼
```

### 3. 更新所有使用 `get_opensearch_client()` 的地方
需要在以下文件中添加 `await`：
- `services/alert_service.py` - 2 處
- `services/retrieval_service.py` - 4 處（包括移除模組級別的客戶端初始化）
- `api/health_check.py` - 1 處

### 4. 修改 `services/retrieval_service.py`
- 移除模組級別的 OpenSearch 客戶端初始化
- 改為在需要時通過 `await get_opensearch_client()` 獲取客戶端

**主要變更：**
```python
# 移除
client = AsyncOpenSearch(...)

# 改為在函數中使用
client = await get_opensearch_client()
response = await client.search(...)
```

## 測試方法
創建了 `test_fix.py` 測試腳本來驗證修復：
1. 測試 OpenSearch 客戶端能否在異步上下文中正確創建
2. 測試排程器的異步包裝器能否正確執行

## 注意事項
1. 所有使用 `get_opensearch_client()` 的函數都必須是異步函數
2. 確保在異步上下文中調用這些函數
3. APScheduler 的 AsyncIOScheduler 需要使用當前的事件循環

## 結果
這些修改確保了：
- aiohttp 的 timeout context manager 在正確的異步任務上下文中使用
- OpenSearch 客戶端在需要時才創建，且在正確的異步上下文中
- 排程器能夠正確地執行異步任務