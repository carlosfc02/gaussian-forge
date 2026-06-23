from fastapi import APIRouter

from app.schemas.pipeline import PipelinePresetRead
from app.services.pipeline_service import list_pipeline_presets

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.get("/presets", response_model=list[PipelinePresetRead])
def get_pipeline_presets():
    return list_pipeline_presets()
