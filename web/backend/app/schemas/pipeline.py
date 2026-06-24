from typing import Literal

from pydantic import BaseModel


class PipelinePresetRead(BaseModel):
    name: str
    frame_step: int
    sequential_overlap: int
    iterations: int
    sugar_mode: str
    sugar_refinement_time: str
    run_sugar: bool


PipelineRunMode = Literal["full", "stage", "custom"]
PipelineStageName = Literal[
    "select_bbox",
    "segment_video",
    "prepare_3dgs_dataset",
    "run_colmap_pipeline",
    "train_3dgs",
    "train_sugar",
    "sugar_metrics",
]


class PipelineAdvancedOptions(BaseModel):
    force: bool | None = None
    metrics: bool | None = None
    maskLoss: bool | None = None
    whiteBackground: bool | None = None

    jobPath: str | None = None
    maskOutputDir: str | None = None
    datasetDir: str | None = None
    gsModelDir: str | None = None
    sugarOutputRoot: str | None = None
    sugarOutputName: str | None = None

    frameIndex: int | None = None
    objectId: int | None = None
    checkpoint: str | None = None
    bboxRunner: Literal["auto", "host", "windows"] | None = None

    frameStep: int | None = None

    matcher: Literal["sequential", "exhaustive"] | None = None
    sequentialOverlap: int | None = None
    cameraModel: str | None = None
    singleCamera: bool | None = None
    useGpu: bool | None = None
    useColmapMasks: bool | None = None
    sparseModel: str | None = None
    skipFeatureExtraction: bool | None = None
    skipMatching: bool | None = None
    skipMapping: bool | None = None
    skipUndistort: bool | None = None

    iterations: int | None = None
    resolution: int | None = None
    eval: bool | None = None
    masksDir: str | None = None

    regularization: Literal["dn_consistency", "density", "sdf"] | None = None
    refinementTime: Literal["short", "medium", "long"] | None = None
    qualityMode: Literal["preset", "low", "high"] | None = None
    surfaceLevel: float | None = None
    nVertices: int | None = None
    gaussiansPerTriangle: int | None = None
    refinementIterations: int | None = None
    squareSize: int | None = None
    gpu: int | None = None
    bboxMin: str | None = None
    bboxMax: str | None = None
    centerBbox: bool | None = None
    exportObj: bool | None = None
    exportPly: bool | None = None
    postprocessMesh: bool | None = None
    postprocessDensityThreshold: float | None = None
    postprocessIterations: int | None = None


class StartPipelineRunRequest(BaseModel):
    preset: str
    mode: PipelineRunMode = "full"
    stage: PipelineStageName | None = None
    stages: list[PipelineStageName] | None = None
    options: PipelineAdvancedOptions | None = None


class PipelineRunRead(BaseModel):
    scene_name: str
    run_name: str
    preset: str
    status: str
    mode: str = "full"
    stage: str | None = None
    stages: list[str] | None = None
    options: dict | None = None
    started_at: str | None = None
    finished_at: str | None = None
    current_stage: str | None = None
    manifest_path: str | None = None
    error: str | None = None


class PipelineStageRead(BaseModel):
    stage: str
    status: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    log_path: str | None = None


class PipelineLogRead(BaseModel):
    scene_name: str
    run_name: str
    stage: str | None = None
    stages: list[PipelineStageRead] = []
    content: str = ""
    truncated: bool = False
    updated_at: str | None = None
