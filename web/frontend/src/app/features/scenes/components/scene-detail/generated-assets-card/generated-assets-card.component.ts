import { Component, Input } from '@angular/core';
import { Scene } from '../../../../../shared/models/scene-data.model';
@Component({ selector: 'app-generated-assets-card', standalone: true, templateUrl: './generated-assets-card.component.html', host: { class: 'scene-detail-card scene-detail-card--assets' } })
export class GeneratedAssetsCardComponent { @Input({ required: true }) scene!: Scene; @Input() assetCount = 0; }