import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "stock-assistant-api")
    app_env: str = os.getenv("APP_ENV", "dev")
    app_version: str = os.getenv("APP_VERSION", "0.1.0")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    postgres_host: str = os.getenv("POSTGRES_HOST", "postgres")
    postgres_port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    redis_host: str = os.getenv("REDIS_HOST", "redis")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    database_url: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///E:/workstation/StockSystem/data/duckdb/stock_assistant.db",
    )
    market_data_provider: str = os.getenv("MARKET_DATA_PROVIDER", "akshare")
    broker_provider: str = os.getenv("BROKER_PROVIDER", "mock")
    llm_provider: str = os.getenv("LLM_PROVIDER", "mock")
    llm_openai_base_url: str = os.getenv("LLM_OPENAI_BASE_URL", "https://api.openai.com/v1")
    llm_openai_model: str = os.getenv("LLM_OPENAI_MODEL", "gpt-4o-mini")
    llm_openai_api_key: str = os.getenv("LLM_OPENAI_API_KEY", "")


settings = Settings()
