import { Component, EventEmitter, Input, Output } from '@angular/core';
import { SceneAssetKind } from '../../../../../core/services/scene-asset.service';
import { Scene } from '../../../../../shared/models/scene-data.model';

@Component({
  selector: 'app-generated-assets-card',
  standalone: true,
  templateUrl: './generated-assets-card.component.html',
  host: { class: 'scene-detail-card scene-detail-card--assets' },
})
export class GeneratedAssetsCardComponent {
  @Input({ required: true }) scene!: Scene;
  @Input() assetCount = 0;
  @Input() downloadingAsset: SceneAssetKind | null = null;
  @Input() actionError: string | null = null;
  @Input() actionMessage: string | null = null;
  @Output() download3dgsPly = new EventEmitter<void>();
  @Output() downloadSugarPly = new EventEmitter<void>();
  @Output() downloadSugarObj = new EventEmitter<void>();
}
