import re 
import shutil
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.core.paths import (
    VIDEOS_DIR,
    MASKS_DIR,
    GS_DIR,
    SUGAR_OUTPUT_DIR,
    LOGS_DIR,
)

from app.schemas.scene import SceneRead, SceneStatus

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}

def sanitaze_scene_name(scene_name: str) -> str:
    cleaned = scene_name.strip().replace(" ", "_")
    cleaned = re.sub(r"[^a-zA-Z0-9_\-]", "", cleaned)

    if not cleaned:
        raise HTTPException(status_code=400, detail="Invalid scene name.")
    return cleaned

def detect_scene_status(scene_name: str) -> SceneStatus:
    video_exists = any(VIDEOS_DIR.glob(f"{scene_name}.*"))
    masks_exists = (MASKS_DIR / scene_name).exists()
    gs_exists = (GS_DIR / scene_name).exists()
    sugar_exists = (SUGAR_OUTPUT_DIR / scene_name).exists()

    if sugar_exists:
        return SceneStatus.SUGAR_READY
    if gs_exists:
        return SceneStatus.DATASET_READY
    if masks_exists:
        return SceneStatus.MASKS_READY
    if video_exists:
        return SceneStatus.VIDEO_UPLOADED

    return SceneStatus.CREATED


def get_scene(scene_name: str) -> SceneRead:
    scene_name = sanitaze_scene_name(scene_name)
    video_file = next(VIDEOS_DIR.glob(f"{scene_name}.*"), None)

    return SceneRead(
        name=scene_name,
        status=detect_scene_status(scene_name),
        video_path=str(video_file) if video_file else None,
        masks_path=str(MASKS_DIR / scene_name) if (MASKS_DIR / scene_name).exists() else None,
        gs_path=str(GS_DIR / scene_name) if (GS_DIR / scene_name).exists() else None,
        sugar_output_path=str(SUGAR_OUTPUT_DIR / scene_name) if (SUGAR_OUTPUT_DIR / scene_name).exists() else None,
    )

def list_scenes() -> list[SceneRead]:
    scenes: list[SceneRead] = []

    for video_path in sorted(VIDEOS_DIR.iterdir()):
        if video_path.is_file() and video_path.suffix in ALLOWED_VIDEO_EXTENSIONS:
            scene_name = video_path.stem
            scenes.append(get_scene(scene_name))
    return scenes

async def create_scene_from_upload(scene_name: str, video: UploadFile) -> SceneRead:
    scene_name = sanitaze_scene_name(scene_name)

    original_filename = video.filename or ""
    video_extension = Path(video.filename).suffix.lower()

    if video_extension not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported video format. Allowed: {sorted(ALLOWED_VIDEO_EXTENSIONS)}")

    target_path = VIDEOS_DIR / f"{scene_name}{video_extension}"
    if target_path.exists():
        raise HTTPException(status_code=409, detail=f"Scene '{scene_name}' already has a video.")
    
    LOGS_DIR.joinpath(scene_name).mkdir(parents=True, exist_ok=True)

    with target_path.open("wb") as buffer:
        shutil.copyfileobj(video.file, buffer)
    return get_scene(scene_name)
