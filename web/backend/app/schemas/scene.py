from enum import Enum
from pydantic import BaseModel

class SceneStatus(str, Enum):
    CREATED = "CREATED"
    VIDEO_UPLOADED = "VIDEO_UPLOADED"
    BBOX_SELECTED = "BBOX_SELECTED"
    SEGMENTING = "SEGMENTING"
    MASKS_READY = "MASKS_READY"
    DATASET_READY = "DATASET_READY"
    COLMAP_READY = "COLMAP_READY"
    TRAINING_3DGS = "TRAINING_3DGS"
    THREE_DGS_READY = "THREE_DGS_READY"
    TRAINING_SUGAR = "TRAINING_SUGAR"
    SUGAR_READY = "SUGAR_READY"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"

class SceneRead(BaseModel):
    name: str
    status: SceneStatus
    video_path: str | None = None
    masks_path: str | None = None
    gs_path: str | None = None
    sugar_output_path: str | None = None
