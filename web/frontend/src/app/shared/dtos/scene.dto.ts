import { SceneStatus } from '../models/scene-status.model';

export interface SceneDto {
    name: string;
    status: SceneStatus;
    video_path: string;
    masks_path: string;
    gs_path: string;
    sugar_output_path: string;
}
