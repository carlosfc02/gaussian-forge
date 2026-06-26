import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile

from app.core.paths import (
    DATA_DIR,
    FRAMES_VIDEOS_DIR,
    GS_DIR,
    LOGS_DIR,
    MASKS_DIR,
    PROJECT_ROOT,
    SCRIPTS_DIR,
    SEGMENTATION_JOBS_DIR,
    SUGAR_OUTPUT_DIR,
    VIDEOS_DIR,
)

from app.schemas.scene import MetricStageRead, SceneMetricsRead, SceneRead, SceneStatus, ViewerLaunchRead

ALLOWED_VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv'}
SUGAR_OBJ_PACKAGE_EXTENSIONS = {'.obj', '.mtl', '.png'}
THUMBNAIL_EXTENSION = '.jpg'
METRIC_STAGE_DIRS = ('bbox_estimate', 'colmap', 'train_3dgs', 'train_sugar')

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
    from app.services.pipeline_service import get_pipeline_scene_status

    pipeline_status = get_pipeline_scene_status(scene_name)
    if pipeline_status is not None:
        return pipeline_status

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
    from app.services.pipeline_service import get_latest_pipeline_run

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
        gs_ply_available=find_latest_3dgs_ply(scene_name) is not None,
        sugar_ply_available=find_refined_sugar_ply(scene_name, include_variants=False) is not None,
        sugar_obj_available=find_refined_sugar_obj(scene_name) is not None,
        pipeline_run=get_latest_pipeline_run(scene_name),
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


def _project_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _latest_json_file(directory: Path) -> Path | None:
    if not directory.is_dir():
        return None

    candidates = [path for path in directory.glob('*.json') if path.is_file()]
    if not candidates:
        return None

    return max(candidates, key=lambda path: path.stat().st_mtime)


def _extract_stage_metrics(payload: dict[str, Any]) -> dict[str, Any] | list[Any] | None:
    if 'metrics' in payload:
        return payload['metrics']
    if 'metrics_3dgs' in payload:
        return {'metrics_3dgs': payload['metrics_3dgs']}
    if 'official_sugar_metrics' in payload:
        return payload['official_sugar_metrics']
    return None


def _extract_stage_artifacts(payload: dict[str, Any]) -> dict[str, Any] | None:
    artifacts = payload.get('artifacts')
    if isinstance(artifacts, dict):
        return artifacts

    output_paths = payload.get('output_paths')
    if isinstance(output_paths, dict):
        return output_paths

    return None


def get_scene_metrics(scene_name: str) -> SceneMetricsRead:
    scene_name = sanitaze_scene_name(scene_name)
    metrics_root = GS_DIR / scene_name / 'metrics'
    stages: list[MetricStageRead] = []
    updated_at: str | None = None
    latest_mtime = 0.0

    for stage in METRIC_STAGE_DIRS:
        latest_file = _latest_json_file(metrics_root / stage)
        if latest_file is None:
            continue

        try:
            payload = json.loads(latest_file.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as error:
            logger.warning('Skipping invalid metrics file %s: %s', latest_file, error)
            continue

        file_mtime = latest_file.stat().st_mtime
        if file_mtime > latest_mtime:
            latest_mtime = file_mtime
            updated_at = datetime.fromtimestamp(file_mtime, timezone.utc).isoformat()

        stages.append(
            MetricStageRead(
                stage=stage,
                status=payload.get('status'),
                started_at=payload.get('started_at'),
                finished_at=payload.get('finished_at'),
                duration_seconds=payload.get('duration_seconds'),
                metrics=_extract_stage_metrics(payload),
                parameters=payload.get('parameters') if isinstance(payload.get('parameters'), dict) else None,
                artifacts=_extract_stage_artifacts(payload),
                source_path=_project_relative(latest_file),
            )
        )

    return SceneMetricsRead(scene_name=scene_name, stages=stages, updated_at=updated_at)


def find_latest_3dgs_ply(scene_name: str) -> tuple[Path, int] | None:
    scene_name = sanitaze_scene_name(scene_name)
    point_cloud_root = GS_DIR / scene_name / 'gs' / 'model' / 'point_cloud'
    if not point_cloud_root.is_dir():
        return None

    candidates: list[tuple[int, Path]] = []
    for iteration_dir in point_cloud_root.glob('iteration_*'):
        match = re.fullmatch(r'iteration_(\d+)', iteration_dir.name)
        point_cloud = iteration_dir / 'point_cloud.ply'
        if match and point_cloud.is_file():
            candidates.append((int(match.group(1)), point_cloud))

    if not candidates:
        return None

    iteration, path = max(candidates, key=lambda candidate: candidate[0])
    return path, iteration


def find_refined_sugar_ply(scene_name: str, include_variants: bool = True) -> Path | None:
    scene_name = sanitaze_scene_name(scene_name)
    exact_scene_dir = SUGAR_OUTPUT_DIR / scene_name
    search_roots = [exact_scene_dir]

    if include_variants and SUGAR_OUTPUT_DIR.is_dir():
        prefix_roots = sorted(
            [path for path in SUGAR_OUTPUT_DIR.glob(f'{scene_name}_*') if path.is_dir()],
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        search_roots.extend(prefix_roots)

    candidates: list[Path] = []
    for root in search_roots:
        refined_root = root / 'refined_ply'
        if refined_root.is_dir():
            candidates.extend(path for path in refined_root.rglob('*.ply') if path.is_file())

    if not candidates:
        return None

    return max(candidates, key=lambda path: path.stat().st_mtime)


def find_refined_sugar_obj(scene_name: str) -> Path | None:
    scene_name = sanitaze_scene_name(scene_name)
    refined_mesh_root = SUGAR_OUTPUT_DIR / scene_name / 'refined_mesh'
    if not refined_mesh_root.is_dir():
        return None

    candidates = [path for path in refined_mesh_root.rglob('*.obj') if path.is_file()]
    if not candidates:
        return None

    return max(candidates, key=lambda path: path.stat().st_mtime)


def build_sugar_obj_archive(scene_name: str) -> Path:
    scene_name = sanitaze_scene_name(scene_name)
    obj_path = find_refined_sugar_obj(scene_name)
    if obj_path is None:
        raise HTTPException(status_code=404, detail=f'No refined SuGaR .obj found for scene {scene_name}.')

    package_files = [
        path
        for path in obj_path.parent.iterdir()
        if path.is_file() and path.suffix.lower() in SUGAR_OBJ_PACKAGE_EXTENSIONS
    ]
    temporary_file = tempfile.NamedTemporaryFile(prefix=f'{scene_name}_sugar_', suffix='.zip', delete=False)
    archive_path = Path(temporary_file.name)
    temporary_file.close()

    try:
        with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(package_files):
                archive.write(path, arcname=path.name)
    except Exception:
        archive_path.unlink(missing_ok=True)
        raise

    return archive_path


def _ensure_removable(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return

    if not os.access(path.parent, os.W_OK | os.X_OK):
        raise PermissionError(str(path.parent))

    if path.is_dir() and not path.is_symlink():
        for directory, _subdirectories, _files in os.walk(path):
            directory_path = Path(directory)
            if not os.access(directory_path, os.W_OK | os.X_OK):
                raise PermissionError(str(directory_path))


def _remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def clear_scene_generated_data(scene_name: str) -> SceneRead:
    from app.services.pipeline_service import ensure_no_active_pipeline

    scene_name = sanitaze_scene_name(scene_name)
    video_file = get_scene_video(scene_name)
    ensure_no_active_pipeline(scene_name)

    targets = [
        resolve_scene_thumbnail_file(scene_name),
        MASKS_DIR / scene_name,
        GS_DIR / scene_name,
        SUGAR_OUTPUT_DIR / scene_name,
        DATA_DIR / 'metrics' / 'segmentation' / scene_name,
        SEGMENTATION_JOBS_DIR / f'{scene_name}_job.json',
        LOGS_DIR / scene_name,
    ]

    try:
        for target in targets:
            _ensure_removable(target)
        for target in targets:
            _remove_path(target)
    except PermissionError as error:
        blocked_path = error.filename or str(error)
        raise HTTPException(
            status_code=409,
            detail=(
                f'Cannot clear generated data because {blocked_path} is not writable. '
                'Fix ownership of artifacts created by root and try again.'
            ),
        ) from error
    except OSError as error:
        raise HTTPException(status_code=409, detail=f'Could not clear generated data: {error}') from error

    return build_scene_read(scene_name, video_file)


def _run_viewer_script(scene_name: str, viewer: str, command: list[str]) -> ViewerLaunchRead:
    logs_dir = LOGS_DIR / scene_name
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f'viewer_{viewer}.log'

    log_header = f"\n[{datetime.now(timezone.utc).isoformat()}] {' '.join(command)}\n"
    try:
        result = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
    except subprocess.TimeoutExpired as error:
        log_path.write_text(log_header + (error.stdout or '') + (error.stderr or ''), encoding='utf-8')
        raise HTTPException(status_code=504, detail=f'{viewer} viewer script did not finish its launch step in time.') from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=409, detail=f'Could not execute {command[0]}. Is Bash available?') from error

    with log_path.open('a', encoding='utf-8') as log_handle:
        log_handle.write(log_header)
        if result.stdout:
            log_handle.write(result.stdout)
        if result.stderr:
            log_handle.write(result.stderr)

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or f'{viewer} viewer script failed.').strip()
        raise HTTPException(status_code=409, detail=detail)

    return ViewerLaunchRead(
        scene_name=scene_name,
        viewer=viewer,
        status='launched',
        message=f'{viewer} viewer launch requested. Check the Linux/WSL desktop for the viewer window.',
        command=command,
    )


def _viewer_script_path(script_name: str) -> Path:
    script_path = SCRIPTS_DIR / script_name
    if not script_path.is_file():
        raise HTTPException(status_code=409, detail=f'Viewer launcher script not found: {_project_relative(script_path)}')
    return script_path

def launch_3dgs_viewer(scene_name: str) -> ViewerLaunchRead:
    scene_name = sanitaze_scene_name(scene_name)
    model_dir = GS_DIR / scene_name / 'gs' / 'model'
    source_dir = GS_DIR / scene_name / 'gs' / 'source'

    if not model_dir.is_dir():
        raise HTTPException(status_code=404, detail=f'3DGS model directory not found: {_project_relative(model_dir)}')
    if not source_dir.is_dir():
        raise HTTPException(status_code=404, detail=f'3DGS source directory not found: {_project_relative(source_dir)}')

    script_path = _viewer_script_path('open_3dgs_viewer.sh')
    command = ['bash', str(script_path), '--scene-dir', f'3dgs/{scene_name}']
    return _run_viewer_script(scene_name, '3dgs', command)


def launch_sugar_viewer(scene_name: str) -> ViewerLaunchRead:
    scene_name = sanitaze_scene_name(scene_name)
    source_dir = GS_DIR / scene_name / 'gs' / 'source'
    model_dir = GS_DIR / scene_name / 'gs' / 'model'
    sugar_ply = find_refined_sugar_ply(scene_name)

    if sugar_ply is None:
        raise HTTPException(status_code=404, detail=f'No refined SuGaR .ply found for scene {scene_name}.')
    if not source_dir.is_dir():
        raise HTTPException(status_code=404, detail=f'3DGS source directory not found: {_project_relative(source_dir)}')
    if not model_dir.is_dir():
        raise HTTPException(status_code=404, detail=f'3DGS model directory not found: {_project_relative(model_dir)}')

    script_path = _viewer_script_path('open_sugar_viewer.sh')
    command = [
        'bash',
        str(script_path),
        '--ply-path',
        _project_relative(sugar_ply),
        '--source-dir',
        f'3dgs/{scene_name}/gs/source',
        '--base-model-dir',
        f'3dgs/{scene_name}/gs/model',
    ]
    return _run_viewer_script(scene_name, 'sugar', command)
