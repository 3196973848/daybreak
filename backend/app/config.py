import json
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
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PLANAGENT_",
        extra="ignore",
        env_file=_CONF_FILE if _CONF_FILE.exists() else None,
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
    custom_providers: str = "[]"  # JSON string

    @property
    def available_models(self) -> list[str]:
        return [
            model.strip()
            for model in self.llm_models.split(",")
            if model.strip()
        ]

    def get_custom_providers(self) -> list[dict]:
        try:
            return json.loads(self.custom_providers) if self.custom_providers else []
        except (json.JSONDecodeError, TypeError):
            return []

    def _find_provider_preset(self, provider: str) -> dict:
        """Find provider preset from built-in or custom providers."""
        if provider in LLM_PROVIDERS:
            return LLM_PROVIDERS[provider]
        for cp in self.get_custom_providers():
            if cp.get("id") == provider:
                return cp
        return {}

    def provider_info(self, provider: str | None = None) -> dict:
        provider = provider or self.llm_provider
        preset = self._find_provider_preset(provider)
        base_url = preset.get("base_url") or self.llm_base_url
        is_custom = "key_env" not in preset and "api_key" in preset
        if is_custom:
            # Custom provider: use its own api_key first, then global
            api_key = preset.get("api_key") or self.llm_api_key
        else:
            # Built-in provider: use global key, then env var
            api_key = self.llm_api_key
            if not api_key and preset.get("key_env"):
                api_key = os.environ.get(preset["key_env"], "")
        # For current provider, prefer available_models from config
        if provider == self.llm_provider and self.available_models:
            models = self.available_models
        else:
            models = preset.get("models", [])
        return {
            "provider": provider,
            "name": preset.get("name", provider),
            "base_url": base_url,
            "api_key": api_key,
            "requires_key": preset.get("requires_key", bool(preset.get("key_env"))),
            "models": models,
        }

    def available_providers(self) -> list[dict]:
        result = []
        for provider_id, preset in LLM_PROVIDERS.items():
            result.append({
                "id": provider_id,
                "name": preset["name"],
                "base_url": preset.get("base_url", ""),
                "requires_key": bool(preset.get("key_env")),
                "is_custom": False,
                "models": (
                    self.available_models
                    if provider_id == self.llm_provider and self.available_models
                    else preset.get("models", [])
                ),
            })
        for cp in self.get_custom_providers():
            result.append({
                "id": cp["id"],
                "name": cp.get("name", cp["id"]),
                "base_url": cp.get("base_url", ""),
                "requires_key": True,
                "is_custom": True,
                "models": cp.get("models", []),
            })
        return result

    def add_custom_provider(self, provider: dict) -> None:
        custom = self.get_custom_providers()
        # Remove existing with same id
        custom = [p for p in custom if p.get("id") != provider["id"]]
        custom.append(provider)
        self.custom_providers = json.dumps(custom, ensure_ascii=False)

    def remove_custom_provider(self, provider_id: str) -> None:
        custom = self.get_custom_providers()
        custom = [p for p in custom if p.get("id") != provider_id]
        self.custom_providers = json.dumps(custom, ensure_ascii=False)

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
        "PLANAGENT_CUSTOM_PROVIDERS": settings.custom_providers,
    }
    lines.update(overrides)
    content = "\n".join(f"{key}={value}" for key, value in lines.items()) + "\n"
    _CONF_FILE.write_text(content, encoding="utf-8")
