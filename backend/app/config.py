from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./planagent.db"
    blocks_per_day: int = 2
    hours_per_block: float = 1.0
    # LLM 配置(DeepSeek,OpenAI 兼容接口)
    llm_model: str = "deepseek-v4-pro"
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("PLANAGENT_LLM_API_KEY", "DEEPSEEK_API_KEY"),
    )

    model_config = {"env_prefix": "PLANAGENT_", "extra": "ignore"}


settings = Settings()
