from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./planagent.db"
    blocks_per_day: int = 2
    hours_per_block: float = 1.0
    # LLM 配置(DeepSeek,OpenAI 兼容接口)
    llm_model: str = "deepseek-v4pro"
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""

    model_config = {"env_prefix": "PLANAGENT_"}


settings = Settings()
