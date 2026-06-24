from enum import Enum
from typing import Any

from pydantic import BaseModel

from app.schemas.pipeline import PipelineRunRead

class SceneStatus(str, Enum):
    CREATED = "CREATED"
    VIDEO_UPLOADED = "VIDEO_UPLOADED"
    BBOX_SELECTED = "BBOX_SELECTED"
    SEGMENTING = "SEGMENTING"
    MASKS_READY = "MASKS_READY"
    DATASET_READY = "DATASET_READY"
    COLMAP_RUNNING = "COLMAP_RUNNING"
    COLMAP_READY = "COLMAP_READY"
    TRAINING_3DGS = "TRAINING_3DGS"
    THREE_DGS_READY = "THREE_DGS_READY"
    TRAINING_SUGAR = "TRAINING_SUGAR"
    SUGAR_READY = "SUGAR_READY"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"
    CANCELED = "CANCELED"

class SceneRead(BaseModel):
    name: str
    status: SceneStatus
    video_path: str | None = None
    masks_path: str | None = None
    gs_path: str | None = None
    sugar_output_path: str | None = None
    pipeline_run: PipelineRunRead | None = None


class MetricStageRead(BaseModel):
    stage: str
    status: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    duration_seconds: float | None = None
    metrics: dict[str, Any] | list[Any] | None = None
    parameters: dict[str, Any] | None = None
    artifacts: dict[str, Any] | None = None
    source_path: str


class SceneMetricsRead(BaseModel):
    scene_name: str
    stages: list[MetricStageRead]
    updated_at: str | None = None


class ViewerLaunchRead(BaseModel):
    scene_name: str
    viewer: str
    status: str
    message: str
    command: list[str]
