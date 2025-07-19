"""
OpenSearch 服務模組
集中管理 OpenSearch 客戶端和相關操作
"""

import logging
from typing import Optional
from opensearchpy import AsyncOpenSearch, AsyncHttpConnection

from ..core.config import (
    OPENSEARCH_URL, OPENSEARCH_USER, OPENSEARCH_PASSWORD,
    OPENSEARCH_MAX_CONNECTIONS, OPENSEARCH_CONNECTION_TIMEOUT
)

logger = logging.getLogger(__name__)

# 全域 OpenSearch 客戶端實例
_client: Optional[AsyncOpenSearch] = None

def get_opensearch_client() -> AsyncOpenSearch:
    """
    獲取 OpenSearch 客戶端實例（單例模式）
    
    Returns:
        AsyncOpenSearch: 配置好的 OpenSearch 客戶端
    """
    global _client
    
    if _client is None:
        _client = AsyncOpenSearch(
            hosts=[OPENSEARCH_URL],
            http_auth=(OPENSEARCH_USER, OPENSEARCH_PASSWORD),
            use_ssl=True,
            verify_certs=False,           # 開發環境跳過 SSL 憑證驗證
            ssl_show_warn=False,          # 隱藏 SSL 警告訊息
            connection_class=AsyncHttpConnection,
            # 連接池優化配置
            pool_maxsize=OPENSEARCH_MAX_CONNECTIONS,
            max_retries=3,
            retry_on_timeout=True,
            timeout=OPENSEARCH_CONNECTION_TIMEOUT
        )
        logger.info(f"OpenSearch 客戶端已初始化: {OPENSEARCH_URL}")
    
    return _client

async def close_opensearch_client():
    """關閉 OpenSearch 客戶端連接"""
    global _client
    
    if _client is not None:
        await _client.close()
        _client = None
        logger.info("OpenSearch 客戶端已關閉")

async def check_opensearch_connection() -> bool:
    """
    檢查 OpenSearch 連接是否正常
    
    Returns:
        bool: 連接是否成功
    """
    try:
        client = get_opensearch_client()
        await client.info()
        return True
    except Exception as e:
        logger.error(f"OpenSearch 連接檢查失敗: {str(e)}")
        return False

async def ensure_index_exists(index_name: str) -> bool:
    """
    確保索引存在
    
    Args:
        index_name: 索引名稱
        
    Returns:
        bool: 索引是否存在
    """
    try:
        client = get_opensearch_client()
        exists = await client.indices.exists(index_name)
        
        if not exists:
            logger.warning(f"索引 {index_name} 不存在")
        
        return exists
    except Exception as e:
        logger.error(f"檢查索引 {index_name} 失敗: {str(e)}")
        return False