import os
import sys
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _runtime_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


_CONF_FILE = _runtime_dir() / "planagent.conf"

LLM_PROVIDERS: dict[str, dict] = {
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "key_env": "DEEPSEEK_API_KEY",
        "models": ["deepseek-v4-pro", "deepseek-chat", "deepseek-reasoner"],
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "key_env": "OPENAI_API_KEY",
        "models": ["gpt-4o-mini", "gpt-4o"],
    },
    "ollama": {
        "name": "Ollama（本地）",
        "base_url": "http://127.0.0.1:11434/v1",
        "key_env": None,
        "models": ["qwen2.5", "llama3.1"],
    },
    "anthropic": {
        "name": "Claude",
        "base_url": "https://api.anthropic.com",
        "key_env": "ANTHROPIC_API_KEY",
        "models": ["claude-sonnet-4-20250514", "claude-haiku-4-5-20251001"],
    },
    "custom": {
        "name": "自定义（OpenAI 兼容）",
        "base_url": "",
        "key_env": None,
        "models": [],
    },
}


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
    llm_provider: str = "deepseek"
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

    def provider_info(self, provider: str | None = None) -> dict:
        provider = provider or self.llm_provider
        preset = LLM_PROVIDERS.get(provider, {})
        base_url = preset.get("base_url") or self.llm_base_url
        api_key = self.llm_api_key
        if not api_key and preset.get("key_env"):
            api_key = os.environ.get(preset["key_env"], "")
        models = self.available_models or preset.get("models", [])
        return {
            "provider": provider,
            "name": preset.get("name", provider),
            "base_url": base_url,
            "api_key": api_key,
            "requires_key": bool(preset.get("key_env")),
            "models": models,
        }

    def available_providers(self) -> list[dict]:
        return [
            {
                "id": provider_id,
                "name": preset["name"],
                "requires_key": bool(preset.get("key_env")),
                "models": (
                    self.available_models
                    if provider_id == self.llm_provider and self.available_models
                    else preset.get("models", [])
                ),
            }
            for provider_id, preset in LLM_PROVIDERS.items()
        ]

    @property
    def configured(self) -> bool:
        info = self.provider_info()
        return not info["requires_key"] or bool(info["api_key"])


settings = Settings()


def save_runtime_conf(**overrides: str) -> None:
    """Persist runtime LLM settings to the local planagent.conf file."""
    lines = {
        "PLANAGENT_LLM_PROVIDER": settings.llm_provider,
        "PLANAGENT_LLM_MODEL": settings.llm_model,
        "PLANAGENT_LLM_API_KEY": settings.llm_api_key,
        "PLANAGENT_LLM_BASE_URL": settings.llm_base_url,
    }
    lines.update(overrides)
    content = "\n".join(f"{key}={value}" for key, value in lines.items()) + "\n"
    _CONF_FILE.write_text(content, encoding="utf-8")
