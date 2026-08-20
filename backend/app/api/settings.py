import re
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


class CustomProviderCreate(BaseModel):
    name: str
    base_url: str
    api_key: str = ""
    models: list[str] = []


def _sanitize_id(name: str) -> str:
    """Generate a safe provider ID from name."""
    return re.sub(r"[^a-z0-9-]", "-", name.lower().strip()).strip("-") or "custom"


def _settings_payload() -> dict:
    info = settings.provider_info()
    return {
        "configured": settings.configured,
        "has_api_key": bool(info["api_key"]),
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
    preset = settings._find_provider_preset(payload.provider)
    if not preset and payload.provider not in [p["id"] for p in settings.available_providers()]:
        raise HTTPException(status_code=422, detail="不支持的提供方")

    api_key_input = (payload.api_key or "").strip()
    if api_key_input:
        api_key = api_key_input
    elif payload.provider == settings.llm_provider:
        api_key = settings.llm_api_key
    else:
        api_key = ""

    base_url = (payload.base_url or "").strip() or preset.get("base_url", "")
    preset_models = preset.get("models", [])
    model = (payload.model or "").strip() or (preset_models[0] if preset_models else settings.llm_model)

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


@router.post("/providers")
def create_custom_provider(payload: CustomProviderCreate):
    provider_id = _sanitize_id(payload.name)
    # Check conflict with built-in providers
    if provider_id in LLM_PROVIDERS:
        raise HTTPException(status_code=409, detail="名称与内置服务商冲突")

    provider = {
        "id": provider_id,
        "name": payload.name.strip(),
        "base_url": payload.base_url.strip(),
        "api_key": payload.api_key.strip(),
        "requires_key": True,
        "models": [m.strip() for m in payload.models if m.strip()],
    }
    settings.add_custom_provider(provider)
    save_runtime_conf()
    return _settings_payload()


@router.delete("/providers/{provider_id}")
def delete_custom_provider(provider_id: str):
    # Cannot delete built-in providers
    if provider_id in LLM_PROVIDERS:
        raise HTTPException(status_code=400, detail="不能删除内置服务商")

    custom = settings.get_custom_providers()
    if not any(p.get("id") == provider_id for p in custom):
        raise HTTPException(status_code=404, detail="自定义服务商不存在")

    # If deleting the active provider, switch to deepseek
    if settings.llm_provider == provider_id:
        settings.llm_provider = "deepseek"
        preset = LLM_PROVIDERS["deepseek"]
        settings.llm_base_url = preset["base_url"]
        settings.llm_model = preset["models"][0]
        save_runtime_conf(
            PLANAGENT_LLM_PROVIDER="deepseek",
            PLANAGENT_LLM_BASE_URL=preset["base_url"],
            PLANAGENT_LLM_MODEL=preset["models"][0],
        )

    settings.remove_custom_provider(provider_id)
    save_runtime_conf()
    return _settings_payload()
