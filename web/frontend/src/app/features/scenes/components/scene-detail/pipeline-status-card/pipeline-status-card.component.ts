import { Component, EventEmitter, Input, Output } from '@angular/core';
import { NgbProgressbarModule } from '@ng-bootstrap/ng-bootstrap';
import { SceneStatusMeta } from '../../../../../shared/utils/scene-presentation';

@Component({
  selector: 'app-pipeline-status-card',
  standalone: true,
  imports: [NgbProgressbarModule],
  templateUrl: './pipeline-status-card.component.html',
  host: { class: 'scene-detail-card scene-detail-card--progress' },
})
export class PipelineStatusCardComponent {
  @Input() sceneName = '';
  @Input() meta: SceneStatusMeta | null = null;
  @Input() canClearGeneratedData = false;
  @Input() isClearingGeneratedData = false;
  @Input() actionError: string | null = null;
  @Input() actionMessage: string | null = null;
  @Output() clearGeneratedData = new EventEmitter<void>();

  confirmClearGeneratedData(): void {
    const confirmed = window.confirm(
      `Clear generated data for ${this.sceneName}? This removes masks, 3DGS, SuGaR, metrics, jobs and logs. The original video and GT data will be kept.`,
    );
    if (confirmed) this.clearGeneratedData.emit();
  }
}
