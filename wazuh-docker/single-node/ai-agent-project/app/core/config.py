"""
系統配置模組
集中管理所有環境變數和系統配置參數
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# === OpenSearch 搜尋引擎連接配置 ===
OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "https://wazuh.indexer:9200")
OPENSEARCH_USER = os.getenv("OPENSEARCH_USER", "admin")
OPENSEARCH_PASSWORD = os.getenv("OPENSEARCH_PASSWORD", "SecretPassword")
OPENSEARCH_MAX_CONNECTIONS = int(os.getenv("OPENSEARCH_MAX_CONNECTIONS", "20"))
OPENSEARCH_CONNECTION_TIMEOUT = int(os.getenv("OPENSEARCH_CONNECTION_TIMEOUT", "30"))

# === Neo4j 圖形資料庫連接配置 ===
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "wazuh-graph-2024")

# === 大型語言模型 (LLM) 提供商配置 ===
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic").lower()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# === 日誌配置 ===
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'

# === 應用程式設定 ===
APP_TITLE = "Wazuh GraphRAG AI Agent"
APP_VERSION = "4.0"
APP_STAGE = "Stage 4 - GraphRAG Implementation"

# === 排程器設定 ===
SCHEDULER_INTERVAL_SECONDS = int(os.getenv("SCHEDULER_INTERVAL_SECONDS", "60"))
SCHEDULER_MISFIRE_GRACE_TIME = int(os.getenv("SCHEDULER_MISFIRE_GRACE_TIME", "30"))

# === 檢索設定 ===
DEFAULT_RETRIEVAL_LIMIT = int(os.getenv("DEFAULT_RETRIEVAL_LIMIT", "10"))
VECTOR_SEARCH_K = int(os.getenv("VECTOR_SEARCH_K", "7"))
TIME_WINDOW_MINUTES = int(os.getenv("TIME_WINDOW_MINUTES", "5"))

def validate_config():
    """驗證必要的配置是否已設置"""
    errors = []
    
    if LLM_PROVIDER == 'gemini' and not GEMINI_API_KEY:
        errors.append("LLM_PROVIDER 設為 'gemini' 但 GEMINI_API_KEY 環境變數未設定")
    
    if LLM_PROVIDER == 'anthropic' and not ANTHROPIC_API_KEY:
        errors.append("LLM_PROVIDER 設為 'anthropic' 但 ANTHROPIC_API_KEY 環境變數未設定")
    
    if errors:
        for error in errors:
            logger.error(error)
        raise ValueError(f"配置驗證失敗: {', '.join(errors)}")
    
    logger.info("配置驗證通過")

def get_config_summary() -> dict:
    """獲取配置摘要"""
    return {
        "app_title": APP_TITLE,
        "app_version": APP_VERSION,
        "app_stage": APP_STAGE,
        "llm_provider": LLM_PROVIDER,
        "opensearch_url": OPENSEARCH_URL,
        "neo4j_uri": NEO4J_URI,
        "scheduler_interval": SCHEDULER_INTERVAL_SECONDS,
        "vector_search_k": VECTOR_SEARCH_K
    }