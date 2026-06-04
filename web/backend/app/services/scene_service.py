import logging
import re
import shutil
import subprocess
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.core.paths import (
    FRAMES_VIDEOS_DIR,
    GS_DIR,
    LOGS_DIR,
    MASKS_DIR,
    SUGAR_OUTPUT_DIR,
    VIDEOS_DIR,
)

from app.schemas.scene import SceneRead, SceneStatus

ALLOWED_VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv'}
THUMBNAIL_EXTENSION = '.jpg'

logger = logging.getLogger(__name__)


def sanitaze_scene_name(scene_name: str) -> str:
    cleaned = scene_name.strip().replace(' ', '_')
    cleaned = re.sub(r'[^a-zA-Z0-9_\-]', '', cleaned)

    if not cleaned:
        raise HTTPException(status_code=400, detail='Invalid scene name.')
    return cleaned


def resolve_scene_video_file(scene_name: str) -> Path | None:
    scene_name = sanitaze_scene_name(scene_name)

    for extension in sorted(ALLOWED_VIDEO_EXTENSIONS):
        candidate = VIDEOS_DIR / f'{scene_name}{extension}'
        if candidate.is_file():
            return candidate

    return None


def resolve_scene_thumbnail_file(scene_name: str) -> Path:
    scene_name = sanitaze_scene_name(scene_name)
    return FRAMES_VIDEOS_DIR / f'{scene_name}{THUMBNAIL_EXTENSION}'


def detect_scene_status(scene_name: str, video_file: Path | None = None) -> SceneStatus:
    video_exists = video_file is not None or resolve_scene_video_file(scene_name) is not None
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


def build_scene_read(scene_name: str, video_file: Path | None = None) -> SceneRead:
    scene_name = sanitaze_scene_name(scene_name)
    video_file = video_file or resolve_scene_video_file(scene_name)

    return SceneRead(
        name=scene_name,
        status=detect_scene_status(scene_name, video_file),
        video_path=str(video_file) if video_file else None,
        masks_path=str(MASKS_DIR / scene_name) if (MASKS_DIR / scene_name).exists() else None,
        gs_path=str(GS_DIR / scene_name) if (GS_DIR / scene_name).exists() else None,
        sugar_output_path=str(SUGAR_OUTPUT_DIR / scene_name)
        if (SUGAR_OUTPUT_DIR / scene_name).exists()
        else None,
    )


def get_scene(scene_name: str) -> SceneRead:
    return build_scene_read(scene_name)


def get_scene_video(scene_name: str) -> Path:
    video_file = resolve_scene_video_file(scene_name)

    if video_file is None:
        raise HTTPException(status_code=404, detail=f"Scene '{scene_name}' does not have an uploaded video.")

    return video_file


def generate_scene_thumbnail(scene_name: str, video_file: Path | None = None) -> Path:
    scene_name = sanitaze_scene_name(scene_name)
    video_file = video_file or resolve_scene_video_file(scene_name)

    if video_file is None:
        raise HTTPException(status_code=404, detail=f"Scene '{scene_name}' does not have an uploaded video.")

    thumbnail_file = resolve_scene_thumbnail_file(scene_name)

    try:
        result = subprocess.run(
            [
                'ffmpeg',
                '-y',
                '-i',
                str(video_file),
                '-frames:v',
                '1',
                str(thumbnail_file),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as error:
        raise RuntimeError('ffmpeg is not installed or not available in PATH.') from error

    if result.returncode != 0 or not thumbnail_file.exists():
        stderr = result.stderr.strip() or 'No ffmpeg stderr output.'
        raise RuntimeError(f'Failed to generate thumbnail for {scene_name}: {stderr}')

    return thumbnail_file


def ensure_scene_thumbnail(scene_name: str) -> Path:
    scene_name = sanitaze_scene_name(scene_name)
    thumbnail_file = resolve_scene_thumbnail_file(scene_name)

    if thumbnail_file.exists():
        return thumbnail_file

    return generate_scene_thumbnail(scene_name)


def get_scene_thumbnail(scene_name: str) -> Path:
    try:
        return ensure_scene_thumbnail(scene_name)
    except HTTPException:
        raise
    except RuntimeError as error:
        logger.exception('Unable to provide thumbnail for scene %s.', scene_name)
        raise HTTPException(status_code=500, detail=str(error)) from error


def list_scenes() -> list[SceneRead]:
    scenes: list[SceneRead] = []

    for video_path in sorted(VIDEOS_DIR.iterdir()):
        if video_path.is_file() and video_path.suffix in ALLOWED_VIDEO_EXTENSIONS:
            scene_name = video_path.stem
            scenes.append(build_scene_read(scene_name, video_path))
    return scenes


async def create_scene_from_upload(scene_name: str, video: UploadFile) -> SceneRead:
    scene_name = sanitaze_scene_name(scene_name)
    video_extension = Path(video.filename or '').suffix.lower()

    if video_extension not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f'Unsupported video format. Allowed: {sorted(ALLOWED_VIDEO_EXTENSIONS)}',
        )

    target_path = VIDEOS_DIR / f'{scene_name}{video_extension}'
    if target_path.exists():
        raise HTTPException(status_code=409, detail=f"Scene '{scene_name}' already has a video.")

    LOGS_DIR.joinpath(scene_name).mkdir(parents=True, exist_ok=True)

    with target_path.open('wb') as buffer:
        shutil.copyfileobj(video.file, buffer)

    try:
        generate_scene_thumbnail(scene_name, target_path)
    except RuntimeError:
        logger.exception('Unable to generate thumbnail after upload for scene %s.', scene_name)

    return get_scene(scene_name)
