import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { PipelineLog } from '../../../../../shared/models/pipeline.model';
@Component({ selector: 'app-pipeline-logs-card', standalone: true, imports: [FormsModule], templateUrl: './pipeline-logs-card.component.html', host: { class: 'scene-detail-card scene-detail-card--logs' } })
export class PipelineLogsCardComponent { @Input() log: PipelineLog | null = null; @Input() selectedStage: string | null = null; @Output() selectedStageChange = new EventEmitter<string>(); stageLabel(stage: string | null): string { return stage ? stage.replace(/_/g, ' ') : 'Active stage'; } }