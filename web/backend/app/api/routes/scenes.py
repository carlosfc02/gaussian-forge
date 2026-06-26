from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from app.schemas.pipeline import PipelineLogRead, PipelineRunRead, StartPipelineRunRequest
from app.schemas.scene import SceneMetricsRead, SceneRead, ViewerLaunchRead
from app.services.pipeline_service import cancel_latest_pipeline_run, get_latest_pipeline_logs, get_latest_pipeline_run, start_pipeline_run
from app.services.scene_service import (
    build_sugar_obj_archive,
    clear_scene_generated_data,
    create_scene_from_upload,
    find_latest_3dgs_ply,
    find_refined_sugar_ply,
    get_scene,
    get_scene_metrics,
    get_scene_thumbnail,
    get_scene_video,
    launch_3dgs_viewer,
    launch_sugar_viewer,
    list_scenes,
    sanitaze_scene_name,
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

@router.get("/{scene_name}/metrics", response_model=SceneMetricsRead)
def get_scene_metrics_by_name(scene_name: str):
    return get_scene_metrics(scene_name)

@router.get('/{scene_name}/assets/3dgs-ply')
def download_scene_3dgs_ply(scene_name: str):
    scene_name = sanitaze_scene_name(scene_name)
    result = find_latest_3dgs_ply(scene_name)
    if result is None:
        raise HTTPException(status_code=404, detail=f'No trained 3DGS .ply found for scene {scene_name}.')
    path, iteration = result
    return FileResponse(
        path=path,
        media_type='application/octet-stream',
        filename=f'{scene_name}_3dgs_iteration_{iteration}.ply',
        content_disposition_type='attachment',
    )


@router.get('/{scene_name}/assets/sugar-ply')
def download_scene_sugar_ply(scene_name: str):
    scene_name = sanitaze_scene_name(scene_name)
    path = find_refined_sugar_ply(scene_name, include_variants=False)
    if path is None:
        raise HTTPException(status_code=404, detail=f'No refined SuGaR .ply found for scene {scene_name}.')
    return FileResponse(
        path=path,
        media_type='application/octet-stream',
        filename=f'{scene_name}_sugar.ply',
        content_disposition_type='attachment',
    )


@router.get('/{scene_name}/assets/sugar-obj')
def download_scene_sugar_obj(scene_name: str):
    scene_name = sanitaze_scene_name(scene_name)
    archive_path = build_sugar_obj_archive(scene_name)
    return FileResponse(
        path=archive_path,
        media_type='application/zip',
        filename=f'{scene_name}_sugar_obj.zip',
        content_disposition_type='attachment',
        background=BackgroundTask(archive_path.unlink, missing_ok=True),
    )


@router.delete('/{scene_name}/data', response_model=SceneRead)
def delete_scene_generated_data(scene_name: str):
    return clear_scene_generated_data(scene_name)


@router.post("/{scene_name}/viewers/3dgs", response_model=ViewerLaunchRead)
def launch_scene_3dgs_viewer(scene_name: str):
    return launch_3dgs_viewer(scene_name)

@router.post("/{scene_name}/viewers/sugar", response_model=ViewerLaunchRead)
def launch_scene_sugar_viewer(scene_name: str):
    return launch_sugar_viewer(scene_name)

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
