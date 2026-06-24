import { ViewerLaunchDto } from '../../shared/dtos/viewer.dto';
import { ViewerLaunch } from '../../shared/models/viewer.model';
export function mapViewerLaunchDto(dto: ViewerLaunchDto): ViewerLaunch { return { sceneName: dto.scene_name, viewer: dto.viewer, status: dto.status, message: dto.message, command: dto.command }; }