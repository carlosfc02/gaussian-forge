import { Component, EventEmitter, Input, OnChanges, Output, SimpleChanges } from '@angular/core';
import { ReactiveFormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { PipelinePreset, PipelinePresetName, PipelineStageName, StartPipelineRunRequest } from '../../../../../shared/models/pipeline.model';
import { AdvancedPipelineFormService, CustomStagePreset, PIPELINE_STAGE_OPTIONS } from '../../../services/advanced-pipeline-form.service';
@Component({ selector: 'app-advanced-pipeline-card', standalone: true, imports: [ReactiveFormsModule, RouterLink], providers: [AdvancedPipelineFormService], templateUrl: './advanced-pipeline-card.component.html', host: { class: 'scene-detail-card scene-detail-card--advanced' } })
export class AdvancedPipelineCardComponent implements OnChanges {
  @Input() presets: PipelinePreset[] = [];
  @Input({ required: true }) selectedPreset!: PipelinePresetName;
  @Input() controlsDisabled = false;
  @Input() canRun = false;
  @Input() isStarting = false;
  @Output() selectedPresetChange = new EventEmitter<PipelinePresetName>();
  @Output() runPipeline = new EventEmitter<StartPipelineRunRequest>();
  readonly stageOptions = PIPELINE_STAGE_OPTIONS;
  constructor(readonly state: AdvancedPipelineFormService) {}
  ngOnChanges(changes: SimpleChanges): void { if (changes['presets'] || changes['selectedPreset']) this.state.configure(this.presets, this.selectedPreset); }
  changePreset(value: string): void { const preset = value as PipelinePresetName; this.state.selectPreset(preset); this.selectedPresetChange.emit(preset); }
  changeRunUntil(value: string): void { this.state.setRunUntil(value as PipelineStageName); }
  toggleStage(stage: PipelineStageName, event: Event): void { this.state.toggleStage(stage, (event.target as HTMLInputElement).checked); }
  applyPreset(preset: CustomStagePreset): void { this.state.applyStagePreset(preset); }
  presetLabel(preset: PipelinePresetName): string { return preset.charAt(0).toUpperCase() + preset.slice(1); }
  submit(): void { const request = this.state.buildRequest(); if (request) this.runPipeline.emit(request); }
}