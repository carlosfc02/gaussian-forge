import { Component, computed, input } from '@angular/core';
import { SceneStatus } from '../../models/scene-status.model';
import { getSceneStatusMeta } from '../../utils/scene-presentation';

@Component({
  selector: 'app-scene-status-badge',
  standalone: true,
  templateUrl: './scene-status-badge.component.html',
  styleUrl: './scene-status-badge.component.scss',
})
export class SceneStatusBadgeComponent {
  readonly status = input.required<SceneStatus>();

  readonly meta = computed(() => getSceneStatusMeta(this.status()));
}
