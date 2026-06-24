import json
import os
import signal
import logging
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status

from app.core.paths import DATA_DIR, LOGS_DIR, PROJECT_ROOT, SCRIPTS_DIR
from app.schemas.pipeline import (
    PipelineAdvancedOptions,
    PipelineLogRead,
    PipelinePresetRead,
    PipelineRunRead,
    PipelineStageRead,
    StartPipelineRunRequest,
)
from app.schemas.scene import SceneStatus

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from pipeline_manifest import build_command_string, utc_now_iso, write_json  # noqa: E402
from pipeline_presets import PRESETS  # noqa: E402

logger = logging.getLogger(__name__)

WEB_RUN_FILENAME = "web_pipeline_run.json"
FULL_MANIFEST_FILENAME = "full_pipeline_manifest.json"
RUNNING_STATUS = "running"
SUCCESS_STATUS = "success"
FAILED_STATUS = "failed"
CANCELED_STATUS = "canceled"
LOG_TAIL_CHARS = 60000

PIPELINE_STAGE_ORDER = [
    "select_bbox",
    "segment_video",
    "prepare_3dgs_dataset",
    "run_colmap_pipeline",
    "train_3dgs",
    "train_sugar",
    "sugar_metrics",
]
PIPELINE_STAGE_SKIP_FLAGS = {
    "select_bbox": "--skip-bbox",
    "segment_video": "--skip-segmentation",
    "prepare_3dgs_dataset": "--skip-prepare",
    "run_colmap_pipeline": "--skip-colmap",
    "train_3dgs": "--skip-3dgs",
    "train_sugar": "--skip-sugar",
}

PIPELINE_STAGE_SKIPS: dict[str, list[str]] = {
    "select_bbox": ["--skip-segmentation", "--skip-prepare", "--skip-colmap", "--skip-3dgs", "--skip-sugar"],
    "segment_video": ["--skip-bbox", "--skip-prepare", "--skip-colmap", "--skip-3dgs", "--skip-sugar"],
    "prepare_3dgs_dataset": ["--skip-bbox", "--skip-segmentation", "--skip-colmap", "--skip-3dgs", "--skip-sugar"],
    "run_colmap_pipeline": ["--skip-bbox", "--skip-segmentation", "--skip-prepare", "--skip-3dgs", "--skip-sugar"],
    "train_3dgs": ["--skip-bbox", "--skip-segmentation", "--skip-prepare", "--skip-colmap", "--skip-sugar"],
    "train_sugar": ["--skip-bbox", "--skip-segmentation", "--skip-prepare", "--skip-colmap", "--skip-3dgs"],
    "sugar_metrics": ["--skip-bbox", "--skip-segmentation", "--skip-prepare", "--skip-colmap", "--skip-3dgs", "--skip-sugar"],
}

POSITIVE_INT_FIELDS = {
    "objectId",
    "frameStep",
    "sequentialOverlap",
    "iterations",
    "resolution",
    "nVertices",
    "gaussiansPerTriangle",
    "refinementIterations",
    "squareSize",
    "postprocessIterations",
}
NON_NEGATIVE_INT_FIELDS = {"frameIndex", "gpu"}
POSITIVE_FLOAT_FIELDS = {"surfaceLevel"}
NON_NEGATIVE_FLOAT_FIELDS = {"postprocessDensityThreshold"}
DATA_PATH_FIELDS = {"maskOutputDir", "datasetDir", "gsModelDir", "sugarOutputRoot"}


def list_pipeline_presets() -> list[PipelinePresetRead]:
    return [
        PipelinePresetRead(name=name, **preset.as_dict())
        for name, preset in PRESETS.items()
    ]


def validate_pipeline_preset(preset: str) -> str:
    if preset not in PRESETS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported pipeline preset. Allowed: {sorted(PRESETS)}",
        )
    return preset


def default_run_name() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def scene_log_dir(scene_name: str) -> Path:
    return LOGS_DIR / scene_name


def run_log_dir(scene_name: str, run_name: str) -> Path:
    return scene_log_dir(scene_name) / run_name


def read_json_file(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        logger.exception("Unable to read pipeline metadata from %s.", path)
        return None


def latest_stage(manifest: dict | None) -> tuple[str | None, str | None]:
    stages = manifest.get("stages", []) if manifest else []
    if not isinstance(stages, list):
        return None, None

    for stage in reversed(stages):
        if isinstance(stage, dict) and stage.get("status") == RUNNING_STATUS:
            return str(stage.get("stage")), RUNNING_STATUS

    for stage in reversed(stages):
        if isinstance(stage, dict) and stage.get("stage"):
            return str(stage.get("stage")), str(stage.get("status") or "")

    return None, None


def normalize_run_status(raw_status: str | None) -> str:
    if raw_status == SUCCESS_STATUS:
        return SUCCESS_STATUS
    if raw_status == FAILED_STATUS:
        return FAILED_STATUS
    if raw_status == CANCELED_STATUS:
        return CANCELED_STATUS
    return RUNNING_STATUS


def build_pipeline_run_read(run_dir: Path) -> PipelineRunRead | None:
    metadata = read_json_file(run_dir / WEB_RUN_FILENAME) or {}
    manifest_path = run_dir / FULL_MANIFEST_FILENAME
    manifest = read_json_file(manifest_path) or {}

    if not metadata and not manifest:
        return None

    stage_name, _stage_status = latest_stage(manifest)
    raw_status = metadata.get("status") if metadata.get("status") == CANCELED_STATUS else manifest.get("status") or metadata.get("status")
    run_status = normalize_run_status(str(raw_status) if raw_status else None)

    return PipelineRunRead(
        scene_name=str(manifest.get("scene_name") or metadata.get("scene_name") or run_dir.parent.name),
        run_name=str(manifest.get("run_name") or metadata.get("run_name") or run_dir.name),
        preset=str(manifest.get("preset") or metadata.get("preset") or "balanced"),
        status=run_status,
        mode=str(metadata.get("mode") or "full"),
        stage=str(metadata.get("stage")) if metadata.get("stage") else None,
        stages=metadata.get("stages") if isinstance(metadata.get("stages"), list) else None,
        options=metadata.get("options") if isinstance(metadata.get("options"), dict) else None,
        started_at=manifest.get("started_at") or metadata.get("started_at"),
        finished_at=manifest.get("finished_at") or metadata.get("finished_at"),
        current_stage=stage_name,
        manifest_path=str(manifest_path) if manifest_path.exists() else None,
        error=manifest.get("error") or metadata.get("error"),
    )


def get_latest_pipeline_run(scene_name: str) -> PipelineRunRead | None:
    root = scene_log_dir(scene_name)
    if not root.is_dir():
        return None

    candidates = [
        path for path in root.iterdir()
        if path.is_dir() and ((path / WEB_RUN_FILENAME).exists() or (path / FULL_MANIFEST_FILENAME).exists())
    ]
    if not candidates:
        return None

    latest_dir = max(candidates, key=lambda path: path.stat().st_mtime)
    return build_pipeline_run_read(latest_dir)


def ensure_no_active_pipeline(scene_name: str) -> None:
    latest_run = get_latest_pipeline_run(scene_name)
    if latest_run and latest_run.status == RUNNING_STATUS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Scene '{scene_name}' already has an active pipeline run.",
        )


def get_pipeline_scene_status(scene_name: str) -> SceneStatus | None:
    run = get_latest_pipeline_run(scene_name)
    if run is None:
        return None
    if run.status == FAILED_STATUS:
        return SceneStatus.ERROR
    if run.status == CANCELED_STATUS:
        return SceneStatus.CANCELED
    stage = run.current_stage
    if run.status == SUCCESS_STATUS:
        if stage == "select_bbox":
            return SceneStatus.BBOX_SELECTED
        if stage == "segment_video":
            return SceneStatus.MASKS_READY
        if stage == "prepare_3dgs_dataset":
            return SceneStatus.DATASET_READY
        if stage == "run_colmap_pipeline":
            return SceneStatus.COLMAP_READY
        if stage == "train_3dgs":
            return SceneStatus.THREE_DGS_READY
        return SceneStatus.SUGAR_READY

    if stage == "select_bbox" or stage is None:
        return SceneStatus.BBOX_SELECTED
    if stage == "segment_video":
        return SceneStatus.SEGMENTING
    if stage == "prepare_3dgs_dataset":
        return SceneStatus.MASKS_READY
    if stage == "run_colmap_pipeline":
        return SceneStatus.COLMAP_RUNNING
    if stage == "train_3dgs":
        return SceneStatus.TRAINING_3DGS
    if stage in {"train_sugar", "sugar_metrics"}:
        return SceneStatus.TRAINING_SUGAR
    return SceneStatus.VIDEO_UPLOADED


def model_to_dict(model: PipelineAdvancedOptions | None) -> dict[str, Any]:
    if model is None:
        return {}
    if hasattr(model, "model_dump"):
        raw = model.model_dump(exclude_none=True)
    else:
        raw = model.dict(exclude_none=True)
    return {key: value for key, value in raw.items() if value != ""}


def ensure_relative_under_root(value: str, root: Path, field: str, base: Path, must_exist: bool = False) -> Path:
    path = Path(value)
    if path.is_absolute():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field} must be a relative path.",
        )
    resolved = (base / path).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field} must stay under {root}.",
        ) from exc
    if must_exist and not resolved.exists():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field} does not exist: {value}",
        )
    return resolved


def ordered_pipeline_stages(stages: list[str]) -> list[str]:
    unknown = [stage for stage in stages if stage not in PIPELINE_STAGE_ORDER]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported pipeline stage. Allowed: {PIPELINE_STAGE_ORDER}",
        )

    seen: set[str] = set()
    duplicates: list[str] = []
    for stage in stages:
        if stage in seen and stage not in duplicates:
            duplicates.append(stage)
        seen.add(stage)
    if duplicates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Duplicate pipeline stages are not allowed: {duplicates}",
        )

    selected = set(stages)
    return [stage for stage in PIPELINE_STAGE_ORDER if stage in selected]


def selected_pipeline_stages(request: StartPipelineRunRequest) -> list[str] | None:
    if request.mode == "stage":
        return [request.stage] if request.stage else None
    if request.mode == "custom":
        raw_stages = list(request.stages or [])
        if not raw_stages:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="stages is required when mode is 'custom'.",
            )
        return ordered_pipeline_stages([str(stage) for stage in raw_stages])
    return None


def custom_stages_need_existing_job(stages: list[str]) -> bool:
    if "select_bbox" in stages:
        return False
    return any(PIPELINE_STAGE_ORDER.index(stage) > 0 for stage in stages)

def validate_advanced_options(scene_name: str, request: StartPipelineRunRequest, options: dict[str, Any]) -> None:
    selected_stages = selected_pipeline_stages(request)
    if request.mode == "stage" and not request.stage:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="stage is required when mode is 'stage'.",
        )

    for field in POSITIVE_INT_FIELDS:
        value = options.get(field)
        if value is not None and int(value) < 1:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field} must be >= 1.")

    for field in NON_NEGATIVE_INT_FIELDS:
        value = options.get(field)
        if value is not None and int(value) < 0:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field} must be >= 0.")

    for field in POSITIVE_FLOAT_FIELDS:
        value = options.get(field)
        if value is not None and float(value) <= 0:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field} must be > 0.")

    for field in NON_NEGATIVE_FLOAT_FIELDS:
        value = options.get(field)
        if value is not None and float(value) < 0:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field} must be >= 0.")

    if options.get("jobPath"):
        ensure_relative_under_root(str(options["jobPath"]), PROJECT_ROOT / "jobs", "jobPath", PROJECT_ROOT)

    if selected_stages and custom_stages_need_existing_job(selected_stages):
        job_path = str(options.get("jobPath") or f"jobs/segmentation/{scene_name}_job.json")
        ensure_relative_under_root(job_path, PROJECT_ROOT / "jobs", "jobPath", PROJECT_ROOT, must_exist=True)

    for field in DATA_PATH_FIELDS:
        if options.get(field):
            ensure_relative_under_root(str(options[field]), DATA_DIR, field, DATA_DIR)


def append_value(command: list[str], options: dict[str, Any], field: str, flag: str) -> None:
    value = options.get(field)
    if value is not None:
        command.extend([flag, str(value)])


def append_enabled_flag(command: list[str], options: dict[str, Any], field: str, flag: str) -> None:
    if options.get(field) is True:
        command.append(flag)


def append_optional_bool(command: list[str], options: dict[str, Any], field: str, true_flag: str, false_flag: str) -> None:
    if field not in options:
        return
    command.append(true_flag if options[field] else false_flag)


def append_flag_once(command: list[str], flag: str) -> None:
    if flag not in command:
        command.append(flag)


def append_stage_selection_flags(command: list[str], request: StartPipelineRunRequest) -> None:
    if request.mode == "stage" and request.stage:
        command.extend(PIPELINE_STAGE_SKIPS[request.stage])
        if request.stage == "train_sugar":
            append_flag_once(command, "--run-sugar")
        if request.stage == "sugar_metrics":
            append_flag_once(command, "--metrics")
        return

    if request.mode != "custom":
        return

    selected_stages = selected_pipeline_stages(request) or []
    selected = set(selected_stages)
    for stage, skip_flag in PIPELINE_STAGE_SKIP_FLAGS.items():
        if stage not in selected:
            append_flag_once(command, skip_flag)

    if "train_sugar" in selected:
        append_flag_once(command, "--run-sugar")
    if "sugar_metrics" in selected:
        append_flag_once(command, "--metrics")

def build_pipeline_command(
    scene_name: str,
    video_arg: str,
    run_name: str,
    request: StartPipelineRunRequest,
    options: dict[str, Any],
) -> list[str]:
    command = [
        sys.executable,
        str(SCRIPTS_DIR / "run_full_pipeline.py"),
        "--video",
        video_arg,
        "--scene-name",
        scene_name,
        "--preset",
        request.preset,
        "--run-name",
        run_name,
    ]

    append_stage_selection_flags(command, request)

    for field, flag in (
        ("force", "--force"),
        ("metrics", "--metrics"),
        ("maskLoss", "--mask-loss"),
        ("whiteBackground", "--white-background"),
        ("skipFeatureExtraction", "--skip-feature-extraction"),
        ("skipMatching", "--skip-matching"),
        ("skipMapping", "--skip-mapping"),
        ("skipUndistort", "--skip-undistort"),
        ("eval", "--eval-3dgs"),
    ):
        append_enabled_flag(command, options, field, flag)

    for field, flag in (
        ("jobPath", "--job-path"),
        ("maskOutputDir", "--mask-output-dir"),
        ("datasetDir", "--dataset-dir"),
        ("gsModelDir", "--gs-model-dir"),
        ("sugarOutputName", "--sugar-output-name"),
        ("frameIndex", "--frame-index"),
        ("objectId", "--object-id"),
        ("checkpoint", "--checkpoint"),
        ("bboxRunner", "--bbox-runner"),
        ("frameStep", "--frame-step"),
        ("iterations", "--iterations"),
        ("sequentialOverlap", "--sequential-overlap"),
        ("matcher", "--matcher"),
        ("resolution", "--resolution"),
        ("cameraModel", "--camera-model"),
        ("sparseModel", "--sparse-model"),
        ("masksDir", "--masks-dir"),
        ("sugarOutputRoot", "--sugar-output-root"),
        ("regularization", "--sugar-regularization"),
        ("refinementTime", "--sugar-refinement-time"),
        ("qualityMode", "--sugar-quality-mode"),
        ("surfaceLevel", "--surface-level"),
        ("nVertices", "--n-vertices"),
        ("gaussiansPerTriangle", "--gaussians-per-triangle"),
        ("refinementIterations", "--refinement-iterations"),
        ("squareSize", "--square-size"),
        ("gpu", "--sugar-gpu"),
        ("bboxMin", "--bboxmin"),
        ("bboxMax", "--bboxmax"),
        ("postprocessDensityThreshold", "--postprocess-density-threshold"),
        ("postprocessIterations", "--postprocess-iterations"),
    ):
        append_value(command, options, field, flag)

    append_optional_bool(command, options, "singleCamera", "--single-camera", "--multi-camera")
    append_optional_bool(command, options, "useGpu", "--use-gpu", "--no-use-gpu")
    append_optional_bool(command, options, "useColmapMasks", "--use-colmap-masks", "--no-use-colmap-masks")
    append_optional_bool(command, options, "centerBbox", "--center-bbox", "--no-center-bbox")
    append_optional_bool(command, options, "exportObj", "--export-obj", "--no-export-obj")
    append_optional_bool(command, options, "exportPly", "--export-ply", "--no-export-ply")
    append_optional_bool(command, options, "postprocessMesh", "--postprocess-mesh", "--no-postprocess-mesh")

    return command


def start_pipeline_run(scene_name: str, video_path: Path, request: StartPipelineRunRequest) -> PipelineRunRead:
    request.preset = validate_pipeline_preset(request.preset)
    options = model_to_dict(request.options)
    validate_advanced_options(scene_name, request, options)
    request_stages = selected_pipeline_stages(request)
    ensure_no_active_pipeline(scene_name)

    try:
        video_arg = video_path.resolve().relative_to(DATA_DIR.resolve()).as_posix()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Scene video must live under the GaussianForge data directory.",
        ) from exc

    run_name = default_run_name()
    log_dir = run_log_dir(scene_name, run_name)
    log_dir.mkdir(parents=True, exist_ok=True)
    command = build_pipeline_command(scene_name, video_arg, run_name, request, options)

    metadata = {
        "scene_name": scene_name,
        "run_name": run_name,
        "preset": request.preset,
        "mode": request.mode,
        "stage": request.stage,
        "stages": request_stages,
        "options": options,
        "status": RUNNING_STATUS,
        "started_at": utc_now_iso(),
        "command": build_command_string(command),
    }
    write_json(log_dir / WEB_RUN_FILENAME, metadata)

    try:
        launch_log = (log_dir / "web_pipeline_process.log").open(
            "a",
            encoding="utf-8",
            errors="replace",
        )
        popen_kwargs = {
            "cwd": PROJECT_ROOT,
            "stdout": launch_log,
            "stderr": subprocess.STDOUT,
            "text": True,
        }
        if sys.platform == "win32":
            popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            popen_kwargs["start_new_session"] = True

        process = subprocess.Popen(command, **popen_kwargs)
        launch_log.close()
    except Exception as exc:
        metadata["status"] = FAILED_STATUS
        metadata["finished_at"] = utc_now_iso()
        metadata["error"] = str(exc)
        write_json(log_dir / WEB_RUN_FILENAME, metadata)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to start full pipeline: {exc}",
        ) from exc

    metadata["pid"] = process.pid
    write_json(log_dir / WEB_RUN_FILENAME, metadata)
    run = build_pipeline_run_read(log_dir)
    assert run is not None
    return run


def stage_records(manifest: dict | None) -> list[dict]:
    stages = manifest.get("stages", []) if manifest else []
    return [stage for stage in stages if isinstance(stage, dict)] if isinstance(stages, list) else []


def pipeline_stage_reads(manifest: dict | None) -> list[PipelineStageRead]:
    return [
        PipelineStageRead(
            stage=str(stage.get("stage") or ""),
            status=str(stage.get("status")) if stage.get("status") is not None else None,
            started_at=stage.get("started_at"),
            finished_at=stage.get("finished_at"),
            log_path=str(stage.get("log_path")) if stage.get("log_path") else None,
        )
        for stage in stage_records(manifest)
        if stage.get("stage")
    ]


def choose_log_stage(manifest: dict | None, requested_stage: str | None) -> dict | None:
    stages = stage_records(manifest)
    if requested_stage:
        for stage in stages:
            if stage.get("stage") == requested_stage:
                return stage
        return None

    for stage in reversed(stages):
        if stage.get("status") == RUNNING_STATUS:
            return stage
    return stages[-1] if stages else None


def safe_log_path(run_dir: Path, stage: dict | None) -> Path | None:
    if stage and stage.get("log_path"):
        candidate = Path(str(stage["log_path"])).resolve()
        try:
            candidate.relative_to(run_dir.resolve())
        except ValueError:
            logger.warning("Ignoring log path outside pipeline run directory: %s", candidate)
            return None
        return candidate

    fallback = run_dir / "web_pipeline_process.log"
    return fallback if fallback.exists() else None


def read_log_tail(log_path: Path | None, max_chars: int = LOG_TAIL_CHARS) -> tuple[str, bool]:
    if log_path is None or not log_path.is_file():
        return "", False

    max_bytes = max_chars * 4
    file_size = log_path.stat().st_size
    with log_path.open("rb") as handle:
        if file_size > max_bytes:
            handle.seek(-max_bytes, 2)
        data = handle.read()

    content = data.decode("utf-8", errors="replace")
    truncated = file_size > max_bytes or len(content) > max_chars
    return content[-max_chars:], truncated


def get_latest_pipeline_logs(scene_name: str, stage: str | None = None) -> PipelineLogRead | None:
    root = scene_log_dir(scene_name)
    if not root.is_dir():
        return None

    run = get_latest_pipeline_run(scene_name)
    if run is None:
        return None

    run_dir = run_log_dir(run.scene_name, run.run_name)
    manifest = read_json_file(run_dir / FULL_MANIFEST_FILENAME) or {}
    chosen_stage = choose_log_stage(manifest, stage)
    log_path = safe_log_path(run_dir, chosen_stage)
    content, truncated = read_log_tail(log_path)

    return PipelineLogRead(
        scene_name=run.scene_name,
        run_name=run.run_name,
        stage=str(chosen_stage.get("stage")) if chosen_stage and chosen_stage.get("stage") else None,
        stages=pipeline_stage_reads(manifest),
        content=content,
        truncated=truncated,
        updated_at=utc_now_iso(),
    )


def process_exists(pid: int) -> bool:
    if sys.platform == "win32":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
        return str(pid) in result.stdout

    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def terminate_pipeline_process(pid: int) -> None:
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return

    sent_signal = False
    try:
        os.killpg(pid, signal.SIGTERM)
        sent_signal = True
    except ProcessLookupError:
        pass
    except PermissionError:
        os.kill(pid, signal.SIGTERM)
        sent_signal = True

    if not sent_signal and process_exists(pid):
        os.kill(pid, signal.SIGTERM)
        sent_signal = True

    if not sent_signal:
        return

    time.sleep(1)
    if not process_exists(pid):
        return

    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        if process_exists(pid):
            os.kill(pid, signal.SIGKILL)
    except PermissionError:
        os.kill(pid, signal.SIGKILL)


def cancel_latest_pipeline_run(scene_name: str) -> PipelineRunRead:
    run = get_latest_pipeline_run(scene_name)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scene '{scene_name}' does not have a pipeline run.",
        )
    if run.status != RUNNING_STATUS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Scene '{scene_name}' does not have an active pipeline run.",
        )

    run_dir = run_log_dir(run.scene_name, run.run_name)
    metadata_path = run_dir / WEB_RUN_FILENAME
    manifest_path = run_dir / FULL_MANIFEST_FILENAME
    metadata = read_json_file(metadata_path) or {}
    pid = metadata.get("pid")

    if isinstance(pid, int) and process_exists(pid):
        terminate_pipeline_process(pid)

    finished_at = utc_now_iso()
    metadata.update(
        {
            "status": CANCELED_STATUS,
            "finished_at": finished_at,
            "error": "Pipeline run canceled by user.",
        }
    )
    write_json(metadata_path, metadata)

    manifest = read_json_file(manifest_path) or {}
    if manifest:
        manifest["status"] = CANCELED_STATUS
        manifest["finished_at"] = finished_at
        manifest["error"] = "Pipeline run canceled by user."
        for stage in stage_records(manifest):
            if stage.get("status") == RUNNING_STATUS:
                stage["status"] = CANCELED_STATUS
                stage["finished_at"] = finished_at
                stage["error"] = "Pipeline run canceled by user."
        write_json(manifest_path, manifest)

    canceled_run = build_pipeline_run_read(run_dir)
    assert canceled_run is not None
    return canceled_run
