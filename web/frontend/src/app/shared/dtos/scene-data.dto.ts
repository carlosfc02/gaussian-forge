import { SceneStatus } from '../models/scene-status.model';
import { PipelineRunDto } from './pipeline.dto';

export interface SceneDto {
  name: string;
  status: SceneStatus;
  video_path: string;
  masks_path: string;
  gs_path: string;
  sugar_output_path: string;
  gs_ply_available: boolean;
  sugar_ply_available: boolean;
  sugar_obj_available: boolean;
  pipeline_run: PipelineRunDto | null;
}
