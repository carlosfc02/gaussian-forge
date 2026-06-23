from fastapi import APIRouter, File, Form, UploadFile, status
from fastapi.responses import FileResponse

from app.schemas.pipeline import PipelineLogRead, PipelineRunRead, StartPipelineRunRequest
from app.schemas.scene import SceneRead
from app.services.pipeline_service import cancel_latest_pipeline_run, get_latest_pipeline_logs, get_latest_pipeline_run, start_pipeline_run
from app.services.scene_service import (
    create_scene_from_upload,
    get_scene,
    get_scene_thumbnail,
    get_scene_video,
    list_scenes,
)

router = APIRouter(prefix="/scenes", tags=["scenes"])

@router.get("", response_model=list[SceneRead])
def get_all_scenes():
    return list_scenes()

@router.get("/{scene_name}", response_model=SceneRead)
def get_scene_by_name(scene_name: str):
    return get_scene(scene_name)

@router.get("/{scene_name}/video")
def get_scene_video_by_name(scene_name: str):
    return FileResponse(path=get_scene_video(scene_name))

@router.get("/{scene_name}/thumbnail")
def get_scene_thumbnail_by_name(scene_name: str):
    return FileResponse(path=get_scene_thumbnail(scene_name), media_type="image/jpeg")

@router.get("/{scene_name}/pipeline-runs/latest", response_model=PipelineRunRead | None)
def get_latest_scene_pipeline_run(scene_name: str):
    return get_latest_pipeline_run(scene_name)

@router.get("/{scene_name}/pipeline-runs/latest/logs", response_model=PipelineLogRead | None)
def get_latest_scene_pipeline_logs(scene_name: str, stage: str | None = None):
    return get_latest_pipeline_logs(scene_name, stage)

@router.post("/{scene_name}/pipeline-runs/latest/cancel", response_model=PipelineRunRead)
def cancel_latest_scene_pipeline_run(scene_name: str):
    return cancel_latest_pipeline_run(scene_name)

@router.post("/{scene_name}/pipeline-runs", status_code=status.HTTP_202_ACCEPTED, response_model=PipelineRunRead)
def create_scene_pipeline_run(scene_name: str, request: StartPipelineRunRequest):
    return start_pipeline_run(scene_name, get_scene_video(scene_name), request)

@router.post("", status_code=status.HTTP_201_CREATED, response_model=SceneRead)
async def create_new_scene(
    scene_name: str = Form(...),
    video: UploadFile = File(...),
):
    return await create_scene_from_upload(scene_name, video)
