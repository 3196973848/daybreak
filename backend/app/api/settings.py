from fastapi import APIRouter

from ..config import settings


router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/models")
def list_models():
    return {
        "models": settings.available_models,
        "default": settings.llm_model,
    }
