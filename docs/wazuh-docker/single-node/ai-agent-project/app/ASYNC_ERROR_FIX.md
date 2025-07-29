# 異步錯誤修復總結

## 問題描述

您遇到了兩個主要錯誤：

1. **RuntimeError: Timeout context manager should be used inside a task**
   - 這是 aiohttp 的典型問題，當在沒有 asyncio.Task 上下文的同步環境中執行需要事件迴圈的非同步操作時發生

2. **AttributeError: 'Depends' object has no attribute 'get_stats'**
   - 這是 FastAPI 依賴注入的誤用，直接操作了 Depends 物件而不是它所注入的服務實例

## 修復方案

### 1. 修復 AttributeError (健康檢查問題)

**問題原因**: `health_check.py` 中的 `check_cache_health()` 函數直接調用了 `get_cache_service()`，而不是通過 FastAPI 的依賴注入系統。

**修復內容**:
- 修改 `check_cache_health()` 函數，使其接受 `cache_service` 作為參數
- 修改 `perform_health_check()` 函數，使其接受並傳遞 `cache_service` 參數
- 更新 `/health` 端點，使用依賴注入並改為異步函數

```python
# api/health_check.py
async def check_cache_health(cache_service) -> Dict[str, Any]:
    """檢查快取服務狀態"""
    try:
        if cache_service is None:
            raise ValueError("Cache service 未初始化")
        stats = cache_service.get_stats()
        # ...

async def perform_health_check(cache_service=None) -> Dict[str, Any]:
    # ...
    health_status["components"]["cache_service"] = await check_cache_health(cache_service)
    # ...

# api/endpoints.py
@router.get("/health")
async def health_check(cache_service: CacheService = Depends(get_cache_service)):
    """健康檢查端點 - 返回所有組件的健康狀態"""
    return await perform_health_check(cache_service)
```

### 2. 修復 RuntimeError (異步任務問題)

**問題原因**: 排程器可能在事件迴圈之外被創建，導致異步任務無法正確執行。

**修復內容**:
1. 修改 `get_scheduler()` 函數，接受一個可選的事件迴圈參數
2. 在 `start_scheduler()` 中確保有運行中的事件迴圈
3. 在 `main_new.py` 的 `lifespan` 函數中，在異步上下文中初始化排程器

```python
# core/scheduler.py
def get_scheduler(loop=None) -> AsyncIOScheduler:
    """獲取排程器實例"""
    global scheduler
    if scheduler is None:
        if loop is None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        scheduler = AsyncIOScheduler(event_loop=loop)
    return scheduler

# main_new.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ...
    # 在異步上下文中啟動排程器
    loop = asyncio.get_running_loop()
    scheduler = get_scheduler(loop)
    
    # 添加定時任務
    scheduler.add_job(
        async_job_wrapper,
        'interval', 
        seconds=SCHEDULER_INTERVAL_SECONDS, 
        id='agentic_triage_job', 
        misfire_grace_time=SCHEDULER_MISFIRE_GRACE_TIME
    )
    
    scheduler.start()
    # ...
```

## 測試驗證

創建了 `test_async_fix.py` 測試腳本來驗證修復：
1. 測試 OpenSearch 連接
2. 測試查詢警報功能
3. 測試健康檢查功能

運行測試：
```bash
cd /workspace/wazuh-docker/single-node/ai-agent-project/app
python test_async_fix.py
```

## 注意事項

1. 確保所有異步函數都使用 `await` 調用
2. FastAPI 端點如果調用異步函數，必須定義為 `async def`
3. 排程器必須在事件迴圈上下文中初始化和啟動
4. 依賴注入必須在函數參數中使用，不能在函數體內直接調用

## 部署建議

1. 重新構建 Docker 映像：
   ```bash
   docker-compose -f docker-compose.main.yml build ai-agent
   ```

2. 重新啟動服務：
   ```bash
   docker-compose -f docker-compose.main.yml up -d ai-agent
   ```

3. 監控日誌確認錯誤已解決：
   ```bash
   docker-compose -f docker-compose.main.yml logs -f ai-agent
   ```