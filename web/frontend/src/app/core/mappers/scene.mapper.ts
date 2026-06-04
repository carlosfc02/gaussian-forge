import { SceneDto } from '../../shared/dtos/scene.dto';
import { Scene } from '../../shared/models/scene.model';
import { buildSceneThumbnailUrl, buildSceneVideoUrl } from '../../shared/utils/scene-presentation';

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
    };
}

export function mapSceneDtosToScene(sceneDtos: SceneDto[]): Scene[] {
    return sceneDtos.map(mapSceneDtoToScene);
}
