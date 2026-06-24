import { Component, Input } from '@angular/core';
import { NgbProgressbarModule } from '@ng-bootstrap/ng-bootstrap';
import { SceneStatusMeta } from '../../../../../shared/utils/scene-presentation';
@Component({ selector: 'app-pipeline-status-card', standalone: true, imports: [NgbProgressbarModule], templateUrl: './pipeline-status-card.component.html', host: { class: 'scene-detail-card scene-detail-card--progress' } })
export class PipelineStatusCardComponent { @Input() meta: SceneStatusMeta | null = null; }