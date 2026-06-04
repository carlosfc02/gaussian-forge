import { Component, Input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { NgbDropdownModule, NgbProgressbarModule } from '@ng-bootstrap/ng-bootstrap';
import { Scene } from '../../../../shared/models/scene.model';
import { SceneStatusBadgeComponent } from '../../../../shared/components/scene-status-badge/scene-status-badge.component';
import { SceneVideoThumbnailComponent } from '../../../../shared/components/scene-video-thumbnail/scene-video-thumbnail.component';
import { getSceneAssetCount, getSceneStatusMeta } from '../../../../shared/utils/scene-presentation';

@Component({
  selector: 'app-scenes-list',
  standalone: true,
  imports: [
    RouterLink,
    NgbDropdownModule,
    NgbProgressbarModule,
    SceneStatusBadgeComponent,
    SceneVideoThumbnailComponent,
  ],
  templateUrl: './scenes-list.component.html',
  styleUrl: './scenes-list.component.scss',
})
export class ScenesListComponent {
  @Input({ required: true }) scenes: Scene[] = [];
  @Input() emptyTitle = 'No scenes yet';
  @Input() emptyDescription = 'Create your first reconstruction project to start the pipeline.';

  getAssetCount(scene: Scene): number {
    return getSceneAssetCount(scene);
  }

  getStatusLabel(scene: Scene): string {
    return getSceneStatusMeta(scene.status).label;
  }

  getStage(scene: Scene): string {
    return getSceneStatusMeta(scene.status).stage;
  }

  getDescription(scene: Scene): string {
    return getSceneStatusMeta(scene.status).description;
  }

  getProgress(scene: Scene): number {
    return getSceneStatusMeta(scene.status).progress;
  }

}
