import sys
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _runtime_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


_CONF_FILE = _runtime_dir() / "planagent.conf"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PLANAGENT_",
        extra="ignore",
        env_file=_CONF_FILE,
        env_file_encoding="utf-8",
    )

    database_url: str = f"sqlite:///{(_runtime_dir() / 'planagent.db').as_posix()}"
    blocks_per_day: int = 2
    hours_per_block: float = 1.0
    # LLM 配置(DeepSeek,OpenAI 兼容接口)
    llm_model: str = "deepseek-v4-pro"
    llm_models: str = "deepseek-v4-pro,deepseek-chat,deepseek-reasoner"
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("PLANAGENT_LLM_API_KEY", "DEEPSEEK_API_KEY"),
    )
    auth_secret: str = ""
    auth_session_ttl_days: int = 30
    auth_cookie_secure: bool = False
    auth_enabled: bool = False

    @property
    def available_models(self) -> list[str]:
        return [
            model.strip()
            for model in self.llm_models.split(",")
            if model.strip()
        ]


settings = Settings()
