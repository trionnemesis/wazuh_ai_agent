"""安全代理系統的設定管理。"""
from typing import Dict, List, Optional, Any
from pydantic import BaseSettings, Field, validator
from enum import Enum
import os


class LLMProvider(str, Enum):
    """支援的 LLM 供應商。"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class MessageBrokerType(str, Enum):
    """支援的訊息代理類型。"""
    RABBITMQ = "rabbitmq"
    KAFKA = "kafka"


class AgentConfig(BaseSettings):
    """個別代理的設定。"""
    
    # LLM 設定
    llm_provider: LLMProvider
    llm_model: str
    llm_temperature: float = 0.1
    llm_max_tokens: int = 2000
    
    # 效能設定
    max_concurrent_tasks: int = 10
    task_timeout_seconds: int = 300
    retry_attempts: int = 3
    
    class Config:
        env_prefix = "AGENT_"


class Settings(BaseSettings):
    """全域系統設定。"""
    
    # 環境
    environment: str = Field(default="production", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")
    
    # 訊息代理設定
    broker_type: MessageBrokerType = Field(default=MessageBrokerType.RABBITMQ)
    broker_host: str = Field(default="localhost", env="BROKER_HOST")
    broker_port: int = Field(default=5672, env="BROKER_PORT")
    broker_username: str = Field(default="guest", env="BROKER_USERNAME")
    broker_password: str = Field(default="guest", env="BROKER_PASSWORD")
    
    # 佇列名稱
    hunting_queue: str = "hunting_queue"
    execution_queue: str = "execution_queue"
    dead_letter_queue: str = "dead_letter_queue"
    
    # 代理設定
    manager_config: Dict[str, Any] = {
        "llm_provider": LLMProvider.GOOGLE,
        "llm_model": "gemini-1.5-flash",
        "llm_temperature": 0.0,
        "max_concurrent_tasks": 50,
        "task_timeout_seconds": 60,
    }
    
    hunter_config: Dict[str, Any] = {
        "llm_provider": LLMProvider.OPENAI,
        "llm_model": "gpt-4-turbo-preview",
        "llm_temperature": 0.1,
        "max_concurrent_tasks": 20,
        "task_timeout_seconds": 300,
    }
    
    executor_config: Dict[str, Any] = {
        "llm_provider": LLMProvider.ANTHROPIC,
        "llm_model": "claude-3-opus-20240229",
        "llm_temperature": 0.2,
        "max_concurrent_tasks": 10,
        "task_timeout_seconds": 180,
    }
    
    # GraphRAG 設定
    neo4j_uri: str = Field(default="bolt://localhost:7687", env="NEO4J_URI")
    neo4j_username: str = Field(default="neo4j", env="NEO4J_USERNAME")
    neo4j_password: str = Field(default="password", env="NEO4J_PASSWORD")
    
    # 向量資料庫設定
    chroma_host: str = Field(default="localhost", env="CHROMA_HOST")
    chroma_port: int = Field(default=8000, env="CHROMA_PORT")
    embedding_model: str = Field(default="text-embedding-3-small", env="EMBEDDING_MODEL")
    
    # 外部整合
    slack_webhook_url: Optional[str] = Field(default=None, env="SLACK_WEBHOOK_URL")
    slack_channel: str = Field(default="#security-alerts", env="SLACK_CHANNEL")
    
    # API 金鑰 (從環境載入)
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    google_api_key: Optional[str] = Field(default=None, env="GOOGLE_API_KEY")
    
    # 安全設定
    enable_human_approval: bool = Field(default=True, env="ENABLE_HUMAN_APPROVAL")
    auto_execute_low_risk: bool = Field(default=False, env="AUTO_EXECUTE_LOW_RISK")
    
    # 監控
    prometheus_port: int = Field(default=9090, env="PROMETHEUS_PORT")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    @validator("environment")
    def validate_environment(cls, v):
        """驗證環境值。"""
        allowed = ["development", "staging", "production"]
        if v not in allowed:
            raise ValueError(f"環境必須是 {allowed} 其中之一")
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# 單例實例
settings = Settings()