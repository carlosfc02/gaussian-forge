import { PipelineRun } from './pipeline.model';
import { SceneStatus } from './scene-status.model';

export interface Scene {
  name: string;
  status: SceneStatus;
  videoPath: string | null;
  videoUrl: string | null;
  thumbnailUrl: string | null;
  maskPaths: string | null;
  gsPath: string | null;
  sugarOutputPath: string | null;
  gsPlyAvailable: boolean;
  sugarPlyAvailable: boolean;
  sugarObjAvailable: boolean;
  pipelineRun: PipelineRun | null;
}
