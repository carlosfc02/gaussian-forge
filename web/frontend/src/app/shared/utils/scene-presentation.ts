import { SceneStatus } from '../models/scene-status.model';
import { Scene } from '../models/scene.model';

export interface SceneStatusMeta {
  label: string;
  stage: string;
  description: string;
  progress: number;
  tone: 'neutral' | 'info' | 'success' | 'warning' | 'danger';
  icon: string;
}

const SCENE_STATUS_META: Record<SceneStatus, SceneStatusMeta> = {
  [SceneStatus.CREATED]: {
    label: 'Created',
    stage: 'Project initialized',
    description: 'The scene exists but no source video has been uploaded yet.',
    progress: 4,
    tone: 'neutral',
    icon: 'bi-folder-plus',
  },
  [SceneStatus.VIDEO_UPLOADED]: {
    label: 'Video uploaded',
    stage: 'Input ready',
    description: 'The source video is stored and ready for the next preprocessing step.',
    progress: 14,
    tone: 'info',
    icon: 'bi-camera-video',
  },
  [SceneStatus.BBOX_SELECTED]: {
    label: 'BBox selected',
    stage: 'Object selected',
    description: 'A starting bounding box has been chosen for the tracked object.',
    progress: 24,
    tone: 'info',
    icon: 'bi-bounding-box',
  },
  [SceneStatus.SEGMENTING]: {
    label: 'Segmenting',
    stage: 'SAM2 segmentation',
    description: 'The segmentation pipeline is generating frame masks.',
    progress: 34,
    tone: 'info',
    icon: 'bi-magic',
  },
  [SceneStatus.MASKS_READY]: {
    label: 'Masks ready',
    stage: 'Masks generated',
    description: 'Segmentation masks are available for dataset preparation.',
    progress: 46,
    tone: 'info',
    icon: 'bi-layers',
  },
  [SceneStatus.DATASET_READY]: {
    label: 'Dataset ready',
    stage: '3DGS dataset prepared',
    description: 'The filtered dataset is ready to enter the reconstruction stage.',
    progress: 58,
    tone: 'info',
    icon: 'bi-database',
  },
  [SceneStatus.COLMAP_RUNNING]: {
    label: 'COLMAP running',
    stage: 'Sparse reconstruction',
    description: 'COLMAP is currently estimating camera poses and sparse geometry.',
    progress: 66,
    tone: 'warning',
    icon: 'bi-activity',
  },
  [SceneStatus.COLMAP_READY]: {
    label: 'COLMAP ready',
    stage: 'Sparse reconstruction ready',
    description: 'Sparse geometry is available and ready for Gaussian training.',
    progress: 74,
    tone: 'info',
    icon: 'bi-diagram-3',
  },
  [SceneStatus.TRAINING_3DGS]: {
    label: 'Training 3DGS',
    stage: 'Gaussian training',
    description: 'The 3D Gaussian Splatting model is actively training.',
    progress: 84,
    tone: 'warning',
    icon: 'bi-cpu',
  },
  [SceneStatus.THREE_DGS_READY]: {
    label: '3DGS ready',
    stage: 'Gaussian checkpoint ready',
    description: 'A 3DGS checkpoint has been produced and can feed later stages.',
    progress: 90,
    tone: 'success',
    icon: 'bi-stars',
  },
  [SceneStatus.TRAINING_SUGAR]: {
    label: 'Training SuGaR',
    stage: 'Surface refinement',
    description: 'SuGaR is refining the geometry into a mesh-oriented output.',
    progress: 96,
    tone: 'warning',
    icon: 'bi-boxes',
  },
  [SceneStatus.SUGAR_READY]: {
    label: 'SuGaR ready',
    stage: 'Surface reconstruction ready',
    description: 'A SuGaR output exists and the mesh stage is available.',
    progress: 100,
    tone: 'success',
    icon: 'bi-gem',
  },
  [SceneStatus.COMPLETED]: {
    label: 'Completed',
    stage: 'Pipeline completed',
    description: 'The scene finished the end-to-end reconstruction workflow.',
    progress: 100,
    tone: 'success',
    icon: 'bi-check-circle',
  },
  [SceneStatus.ERROR]: {
    label: 'Error',
    stage: 'Needs attention',
    description: 'The scene encountered a failure and requires intervention.',
    progress: 100,
    tone: 'danger',
    icon: 'bi-exclamation-triangle',
  },
  [SceneStatus.CANCELED]: {
    label: 'Canceled',
    stage: 'Pipeline canceled',
    description: 'The active pipeline run was canceled by the user.',
    progress: 100,
    tone: 'warning',
    icon: 'bi-stop-circle',
  },};

export function getSceneStatusMeta(status: SceneStatus): SceneStatusMeta {
  return SCENE_STATUS_META[status];
}

export function buildSceneVideoUrl(sceneName: string, videoPath: string | null): string | null {
  return videoPath ? `/api/scenes/${encodeURIComponent(sceneName)}/video` : null;
}

export function buildSceneThumbnailUrl(sceneName: string, videoPath: string | null): string | null {
  return videoPath ? `/api/scenes/${encodeURIComponent(sceneName)}/thumbnail` : null;
}

export function getSceneAssetCount(scene: Scene): number {
  return [scene.videoPath, scene.maskPaths, scene.gsPath, scene.sugarOutputPath].filter(Boolean).length;
}

export function isSceneTerminal(status: SceneStatus): boolean {
  return [SceneStatus.COMPLETED, SceneStatus.ERROR, SceneStatus.CANCELED, SceneStatus.SUGAR_READY].includes(status);
}

export function isSceneHealthy(status: SceneStatus): boolean {
  return status !== SceneStatus.ERROR;
}
