import { Component, EventEmitter, Input, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { PipelinePreset, PipelinePresetName, PipelineRun } from '../../../../../shared/models/pipeline.model';
@Component({ selector: 'app-pipeline-run-card', standalone: true, imports: [FormsModule], templateUrl: './pipeline-run-card.component.html', host: { class: 'scene-detail-card scene-detail-card--pipeline-run' } })
export class PipelineRunCardComponent {
  @Input() run: PipelineRun | null = null;
  @Input() presets: PipelinePreset[] = [];
  @Input({ required: true }) selectedPreset!: PipelinePresetName;
  @Input() canRun = false;
  @Input() isStarting = false;
  @Input() isCanceling = false;
  @Input() actionError: string | null = null;
  @Input() actionMessage: string | null = null;
  @Output() selectedPresetChange = new EventEmitter<PipelinePresetName>();
  @Output() runPipeline = new EventEmitter<void>();
  @Output() cancelPipeline = new EventEmitter<void>();
  get isRunning(): boolean { return this.run?.status === 'running'; }
  presetLabel(preset: PipelinePresetName): string { return preset.charAt(0).toUpperCase() + preset.slice(1); }
  presetSummary(preset: PipelinePreset): string { return `${preset.iterations.toLocaleString()} iterations, frames every ${preset.frameStep}, ${preset.runSugar ? `${preset.sugarRefinementTime} SuGaR` : 'skips SuGaR'}`; }
  stageLabel(stage: string): string { return stage.replace(/_/g, ' '); }
}