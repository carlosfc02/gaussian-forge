import { Component, Input } from '@angular/core';
import { SceneVideoThumbnailComponent } from '../../../../../shared/components/scene-video-thumbnail/scene-video-thumbnail.component';
import { Scene } from '../../../../../shared/models/scene-data.model';
@Component({ selector: 'app-source-preview-card', standalone: true, imports: [SceneVideoThumbnailComponent], templateUrl: './source-preview-card.component.html', host: { class: 'scene-detail-card scene-detail-card--media' } })
export class SourcePreviewCardComponent { @Input({ required: true }) scene!: Scene; }