from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./planagent.db"
    blocks_per_day: int = 2
    hours_per_block: float = 1.0
    anthropic_model: str = "claude-opus-4-8"

    model_config = {"env_prefix": "PLANAGENT_"}


settings = Settings()
