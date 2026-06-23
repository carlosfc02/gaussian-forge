import { SceneStatus } from '../models/scene-status.model';
import { PipelineAdvancedOptions, PipelineRunMode, PipelineStageName } from '../models/scene.model';

export type PipelinePresetName = 'fast' | 'balanced' | 'quality';
export type PipelineRunStatus = 'running' | 'success' | 'failed' | 'canceled';

export interface StartPipelineRunRequestDto {
    preset: PipelinePresetName;
    mode?: PipelineRunMode;
    stage?: PipelineStageName | null;
    options?: PipelineAdvancedOptions | null;
}

export interface PipelineRunDto {
    scene_name: string;
    run_name: string;
    preset: PipelinePresetName;
    status: PipelineRunStatus;
    mode: PipelineRunMode;
    stage: PipelineStageName | null;
    options: PipelineAdvancedOptions | null;
    started_at: string | null;
    finished_at: string | null;
    current_stage: string | null;
    manifest_path: string | null;
    error: string | null;
}


export interface PipelineStageDto {
    stage: string;
    status: string | null;
    started_at: string | null;
    finished_at: string | null;
    log_path: string | null;
}

export interface PipelineLogDto {
    scene_name: string;
    run_name: string;
    stage: string | null;
    stages: PipelineStageDto[];
    content: string;
    truncated: boolean;
    updated_at: string | null;
}

export interface PipelinePresetDto {
    name: PipelinePresetName;
    frame_step: number;
    sequential_overlap: number;
    iterations: number;
    sugar_mode: string;
    sugar_refinement_time: string;
}

export interface SceneDto {
    name: string;
    status: SceneStatus;
    video_path: string;
    masks_path: string;
    gs_path: string;
    sugar_output_path: string;
    pipeline_run: PipelineRunDto | null;
}
