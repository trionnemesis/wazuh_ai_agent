"""Configuration management for the Security Agent System."""
from typing import Dict, List, Optional, Any
from pydantic_settings import BaseSettings
from pydantic import Field, validator
from enum import Enum
import os


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class MessageBrokerType(str, Enum):
    """Supported message broker types."""
    RABBITMQ = "rabbitmq"
    KAFKA = "kafka"


class AgentConfig(BaseSettings):
    """Configuration for individual agents."""
    
    # LLM Configuration
    llm_provider: LLMProvider
    llm_model: str
    llm_temperature: float = 0.1
    llm_max_tokens: int = 2000
    
    # Performance Configuration
    max_concurrent_tasks: int = 10
    task_timeout_seconds: int = 300
    retry_attempts: int = 3
    
    class Config:
        env_prefix = "AGENT_"


class Settings(BaseSettings):
    """Global system configuration."""
    
    # Environment
    environment: str = Field(default="production", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")
    
    # Message Broker Configuration
    broker_type: MessageBrokerType = Field(default=MessageBrokerType.RABBITMQ)
    broker_host: str = Field(default="localhost", env="BROKER_HOST")
    broker_port: int = Field(default=5672, env="BROKER_PORT")
    broker_username: str = Field(default="guest", env="BROKER_USERNAME")
    broker_password: str = Field(default="guest", env="BROKER_PASSWORD")
    
    # Queue Names
    hunting_queue: str = "hunting_queue"
    execution_queue: str = "execution_queue"
    dead_letter_queue: str = "dead_letter_queue"
    
    # Agent Configurations
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
    
    # GraphRAG Configuration
    neo4j_uri: str = Field(default="bolt://localhost:7687", env="NEO4J_URI")
    neo4j_username: str = Field(default="neo4j", env="NEO4J_USERNAME")
    neo4j_password: str = Field(default="password", env="NEO4J_PASSWORD")
    
    # Vector Database Configuration
    chroma_host: str = Field(default="localhost", env="CHROMA_HOST")
    chroma_port: int = Field(default=8000, env="CHROMA_PORT")
    embedding_model: str = Field(default="text-embedding-3-small", env="EMBEDDING_MODEL")
    
    # External Integrations
    slack_webhook_url: Optional[str] = Field(default=None, env="SLACK_WEBHOOK_URL")
    slack_channel: str = Field(default="#security-alerts", env="SLACK_CHANNEL")
    
    # API Keys (loaded from environment)
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    google_api_key: Optional[str] = Field(default=None, env="GOOGLE_API_KEY")
    
    # Security Configuration
    enable_human_approval: bool = Field(default=True, env="ENABLE_HUMAN_APPROVAL")
    auto_execute_low_risk: bool = Field(default=False, env="AUTO_EXECUTE_LOW_RISK")
    
    # Monitoring
    prometheus_port: int = Field(default=9090, env="PROMETHEUS_PORT")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    @validator("environment")
    def validate_environment(cls, v):
        """Validate environment value."""
        allowed = ["development", "staging", "production"]
        if v not in allowed:
            raise ValueError(f"Environment must be one of {allowed}")
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Singleton instance
settings = Settings()
