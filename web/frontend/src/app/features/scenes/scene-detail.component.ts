import { Component, inject, ViewEncapsulation } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AdvancedPipelineCardComponent } from './components/scene-detail/advanced-pipeline-card/advanced-pipeline-card.component';
import { GeneratedAssetsCardComponent } from './components/scene-detail/generated-assets-card/generated-assets-card.component';
import { MetricsCardComponent } from './components/scene-detail/metrics-card/metrics-card.component';
import { PipelineLogsCardComponent } from './components/scene-detail/pipeline-logs-card/pipeline-logs-card.component';
import { PipelineRunCardComponent } from './components/scene-detail/pipeline-run-card/pipeline-run-card.component';
import { PipelineStatusCardComponent } from './components/scene-detail/pipeline-status-card/pipeline-status-card.component';
import { SceneDetailHeaderComponent } from './components/scene-detail/scene-detail-header/scene-detail-header.component';
import { SourcePreviewCardComponent } from './components/scene-detail/source-preview-card/source-preview-card.component';
import { ViewersCardComponent } from './components/scene-detail/viewers-card/viewers-card.component';
import { SceneDetailFacade } from './services/scene-detail.facade';

@Component({
  selector: 'app-scene-detail',
  standalone: true,
  imports: [RouterLink, SceneDetailHeaderComponent, SourcePreviewCardComponent, PipelineStatusCardComponent, PipelineRunCardComponent, AdvancedPipelineCardComponent, ViewersCardComponent, MetricsCardComponent, PipelineLogsCardComponent, GeneratedAssetsCardComponent],
  providers: [SceneDetailFacade],
  templateUrl: './scene-detail.component.html',
  styleUrl: './scene-detail.component.scss',
  encapsulation: ViewEncapsulation.None,
})
export class SceneDetailComponent {
  readonly facade = inject(SceneDetailFacade);
}