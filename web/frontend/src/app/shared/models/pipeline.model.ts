export type PipelinePresetName = 'fast' | 'balanced' | 'quality';
export type PipelineRunStatus = 'running' | 'success' | 'failed' | 'canceled';
export type PipelineRunMode = 'full' | 'stage' | 'custom';
export type PipelineStageName =
  | 'select_bbox'
  | 'segment_video'
  | 'prepare_3dgs_dataset'
  | 'run_colmap_pipeline'
  | 'train_3dgs'
  | 'train_sugar'
  | 'sugar_metrics';

export interface PipelineAdvancedOptions {
  force?: boolean | null; metrics?: boolean | null; maskLoss?: boolean | null; whiteBackground?: boolean | null;
  jobPath?: string | null; maskOutputDir?: string | null; datasetDir?: string | null; gsModelDir?: string | null;
  sugarOutputRoot?: string | null; sugarOutputName?: string | null; frameIndex?: number | null; objectId?: number | null;
  checkpoint?: string | null; bboxRunner?: 'auto' | 'host' | 'windows' | null; frameStep?: number | null;
  matcher?: 'sequential' | 'exhaustive' | null; sequentialOverlap?: number | null; cameraModel?: string | null;
  singleCamera?: boolean | null; useGpu?: boolean | null; useColmapMasks?: boolean | null; sparseModel?: string | null;
  skipFeatureExtraction?: boolean | null; skipMatching?: boolean | null; skipMapping?: boolean | null; skipUndistort?: boolean | null;
  iterations?: number | null; resolution?: number | null; eval?: boolean | null; masksDir?: string | null;
  regularization?: 'dn_consistency' | 'density' | 'sdf' | null; refinementTime?: 'short' | 'medium' | 'long' | null;
  qualityMode?: 'preset' | 'low' | 'high' | null; surfaceLevel?: number | null; nVertices?: number | null;
  gaussiansPerTriangle?: number | null; refinementIterations?: number | null; squareSize?: number | null; gpu?: number | null;
  bboxMin?: string | null; bboxMax?: string | null; centerBbox?: boolean | null; exportObj?: boolean | null;
  exportPly?: boolean | null; postprocessMesh?: boolean | null; postprocessDensityThreshold?: number | null;
  postprocessIterations?: number | null;
}

export interface StartPipelineRunRequest { preset: PipelinePresetName; mode?: PipelineRunMode; stage?: PipelineStageName | null; stages?: PipelineStageName[] | null; options?: PipelineAdvancedOptions | null; }
export interface PipelineRun { sceneName: string; runName: string; preset: PipelinePresetName; status: PipelineRunStatus; mode: PipelineRunMode; stage: PipelineStageName | null; stages: PipelineStageName[] | null; options: PipelineAdvancedOptions | null; startedAt: string | null; finishedAt: string | null; currentStage: string | null; manifestPath: string | null; error: string | null; }
export interface PipelineStage { stage: string; status: string | null; startedAt: string | null; finishedAt: string | null; logPath: string | null; }
export interface PipelineLog { sceneName: string; runName: string; stage: string | null; stages: PipelineStage[]; content: string; truncated: boolean; updatedAt: string | null; }
export interface PipelinePreset { name: PipelinePresetName; frameStep: number; sequentialOverlap: number; iterations: number; sugarMode: string; sugarRefinementTime: string; runSugar: boolean; }