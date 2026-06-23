import { PipelineLogDto, PipelinePresetDto, PipelineRunDto, PipelineStageDto, SceneDto } from '../../shared/dtos/scene.dto';
import { PipelineLog, PipelinePreset, PipelineRun, PipelineStage, Scene } from '../../shared/models/scene.model';
import { buildSceneThumbnailUrl, buildSceneVideoUrl } from '../../shared/utils/scene-presentation';


export function mapPipelineStageDtoToPipelineStage(pipelineStageDto: PipelineStageDto): PipelineStage {
    return {
        stage: pipelineStageDto.stage,
        status: pipelineStageDto.status,
        startedAt: pipelineStageDto.started_at,
        finishedAt: pipelineStageDto.finished_at,
        logPath: pipelineStageDto.log_path,
    };
}

export function mapPipelineLogDtoToPipelineLog(pipelineLogDto: PipelineLogDto): PipelineLog {
    return {
        sceneName: pipelineLogDto.scene_name,
        runName: pipelineLogDto.run_name,
        stage: pipelineLogDto.stage,
        stages: pipelineLogDto.stages.map(mapPipelineStageDtoToPipelineStage),
        content: pipelineLogDto.content,
        truncated: pipelineLogDto.truncated,
        updatedAt: pipelineLogDto.updated_at,
    };
}

export function mapPipelineRunDtoToPipelineRun(pipelineRunDto: PipelineRunDto): PipelineRun {
    return {
        sceneName: pipelineRunDto.scene_name,
        runName: pipelineRunDto.run_name,
        preset: pipelineRunDto.preset,
        status: pipelineRunDto.status,
        mode: pipelineRunDto.mode ?? 'full',
        stage: pipelineRunDto.stage ?? null,
        options: pipelineRunDto.options ?? null,
        startedAt: pipelineRunDto.started_at,
        finishedAt: pipelineRunDto.finished_at,
        currentStage: pipelineRunDto.current_stage,
        manifestPath: pipelineRunDto.manifest_path,
        error: pipelineRunDto.error,
    };
}

export function mapPipelinePresetDtoToPipelinePreset(pipelinePresetDto: PipelinePresetDto): PipelinePreset {
    return {
        name: pipelinePresetDto.name,
        frameStep: pipelinePresetDto.frame_step,
        sequentialOverlap: pipelinePresetDto.sequential_overlap,
        iterations: pipelinePresetDto.iterations,
        sugarMode: pipelinePresetDto.sugar_mode,
        sugarRefinementTime: pipelinePresetDto.sugar_refinement_time,
    };
}

export function mapSceneDtoToScene(sceneDto: SceneDto): Scene {
    return {
        name: sceneDto.name,
        status: sceneDto.status,
        videoPath: sceneDto.video_path || null,
        videoUrl: buildSceneVideoUrl(sceneDto.name, sceneDto.video_path || null),
        thumbnailUrl: buildSceneThumbnailUrl(sceneDto.name, sceneDto.video_path || null),
        maskPaths: sceneDto.masks_path || null,
        gsPath: sceneDto.gs_path || null,
        sugarOutputPath: sceneDto.sugar_output_path || null,
        pipelineRun: sceneDto.pipeline_run ? mapPipelineRunDtoToPipelineRun(sceneDto.pipeline_run) : null,
    };
}

export function mapSceneDtosToScene(sceneDtos: SceneDto[]): Scene[] {
    return sceneDtos.map(mapSceneDtoToScene);
}
