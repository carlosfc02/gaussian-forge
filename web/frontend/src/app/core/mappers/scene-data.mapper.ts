import { SceneDto } from '../../shared/dtos/scene-data.dto';
import { Scene } from '../../shared/models/scene-data.model';
import { buildSceneThumbnailUrl, buildSceneVideoUrl } from '../../shared/utils/scene-presentation';
import { mapPipelineRunDto } from './pipeline.mapper';

export function mapSceneDto(dto: SceneDto): Scene {
  return {
    name: dto.name,
    status: dto.status,
    videoPath: dto.video_path || null,
    videoUrl: buildSceneVideoUrl(dto.name, dto.video_path || null),
    thumbnailUrl: buildSceneThumbnailUrl(dto.name, dto.video_path || null),
    maskPaths: dto.masks_path || null,
    gsPath: dto.gs_path || null,
    sugarOutputPath: dto.sugar_output_path || null,
    gsPlyAvailable: dto.gs_ply_available ?? false,
    sugarPlyAvailable: dto.sugar_ply_available ?? false,
    sugarObjAvailable: dto.sugar_obj_available ?? false,
    pipelineRun: dto.pipeline_run ? mapPipelineRunDto(dto.pipeline_run) : null,
  };
}

export function mapSceneDtos(dtos: SceneDto[]): Scene[] {
  return dtos.map(mapSceneDto);
}
