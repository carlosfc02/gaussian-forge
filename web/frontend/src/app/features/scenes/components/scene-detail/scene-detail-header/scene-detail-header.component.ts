import { Component, Input } from '@angular/core';
import { SceneStatusBadgeComponent } from '../../../../../shared/components/scene-status-badge/scene-status-badge.component';
import { Scene } from '../../../../../shared/models/scene-data.model';
import { SceneStatusMeta } from '../../../../../shared/utils/scene-presentation';

@Component({
  selector: 'app-scene-detail-header',
  standalone: true,
  imports: [SceneStatusBadgeComponent],
  templateUrl: './scene-detail-header.component.html',
})
export class SceneDetailHeaderComponent {
  @Input({ required: true }) scene!: Scene;
  @Input() meta: SceneStatusMeta | null = null;
}
