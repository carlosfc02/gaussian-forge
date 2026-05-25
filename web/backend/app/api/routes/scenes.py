from fastapi import APIRouter, File, Form, UploadFile, status

from app.schemas.scene import SceneRead
from app.services.scene_service import (
    create_scene_from_upload,
    get_scene, 
    list_scenes,
)

router = APIRouter(prefix="/scenes", tags=["scenes"])

@router.get("", response_model=list[SceneRead])
def get_all_scenes():
    return list_scenes()

@router.get("/{scene_name}", response_model=SceneRead)
def get_scene_by_name(scene_name: str):
    return get_scene(scene_name)

@router.post("", status_code=status.HTTP_201_CREATED, response_model=SceneRead)
async def create_new_scene(
    scene_name: str = Form(...),
    video: UploadFile = File(...),
):
    return await create_scene_from_upload(scene_name, video)