from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from ..config import LLM_PROVIDERS, save_runtime_conf, settings


router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None


def _settings_payload() -> dict:
    info = settings.provider_info()
    return {
        "configured": settings.configured,
        "provider": info["provider"],
        "providers": settings.available_providers(),
        "model": settings.llm_model,
        "models": info["models"],
        "requires_key": info["requires_key"],
    }


@router.get("")
def read_settings():
    return _settings_payload()


@router.get("/models")
def list_models():
    info = settings.provider_info()
    return {"models": info["models"], "default": settings.llm_model}


@router.post("")
def update_settings(payload: SettingsUpdate):
    if payload.provider not in LLM_PROVIDERS:
        raise HTTPException(status_code=422, detail="不支持的提供方")
    preset = LLM_PROVIDERS[payload.provider]
    api_key = (payload.api_key or "").strip()
    base_url = (payload.base_url or "").strip() or preset.get("base_url", "")
    preset_models = preset.get("models", [])
    model = (payload.model or "").strip() or (preset_models[0] if preset_models else settings.llm_model)
    if settings.available_models and model not in settings.available_models and model not in preset_models:
        raise HTTPException(status_code=422, detail="不支持的模型")

    settings.llm_provider = payload.provider
    settings.llm_api_key = api_key
    settings.llm_base_url = base_url
    settings.llm_model = model
    save_runtime_conf(
        PLANAGENT_LLM_PROVIDER=payload.provider,
        PLANAGENT_LLM_API_KEY=api_key,
        PLANAGENT_LLM_BASE_URL=base_url,
        PLANAGENT_LLM_MODEL=model,
    )
    return _settings_payload()
