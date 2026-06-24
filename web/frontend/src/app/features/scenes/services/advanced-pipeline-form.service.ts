import { computed, inject, Injectable, signal } from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { AbstractControl, FormBuilder } from '@angular/forms';
import { map, startWith } from 'rxjs';
import { PipelineAdvancedOptions, PipelinePreset, PipelinePresetName, PipelineRunMode, PipelineStageName, StartPipelineRunRequest } from '../../../shared/models/pipeline.model';

export type AdvancedGroup = 'bbox' | 'frames' | 'colmap' | 'gs' | 'sugar';
export type CustomStagePreset = 'until_3dgs' | 'segmentation_prepare' | 'clear';
export const PIPELINE_STAGE_OPTIONS: { value: PipelineStageName; label: string }[] = [
  { value: 'select_bbox', label: 'Select bbox' },
  { value: 'segment_video', label: 'Segment video' },
  { value: 'prepare_3dgs_dataset', label: 'Prepare 3DGS dataset' },
  { value: 'run_colmap_pipeline', label: 'Run COLMAP' },
  { value: 'train_3dgs', label: 'Train 3DGS' },
  { value: 'train_sugar', label: 'Train SuGaR' },
  { value: 'sugar_metrics', label: 'SuGaR metrics' },
];

export const FALLBACK_PRESETS: Record<PipelinePresetName, PipelinePreset> = {
  fast: { name: 'fast', frameStep: 4, sequentialOverlap: 10, iterations: 1000, sugarMode: 'low', sugarRefinementTime: 'short', runSugar: false },
  balanced: { name: 'balanced', frameStep: 2, sequentialOverlap: 20, iterations: 7000, sugarMode: 'default', sugarRefinementTime: 'medium', runSugar: true },
  quality: { name: 'quality', frameStep: 1, sequentialOverlap: 40, iterations: 30000, sugarMode: 'high', sugarRefinementTime: 'long', runSugar: true },
};

function optionDefaults(preset: PipelinePreset): Required<PipelineAdvancedOptions> {
  return {
    force: false, metrics: false, maskLoss: false, whiteBackground: false,
    jobPath: '', maskOutputDir: '', datasetDir: '', gsModelDir: '', sugarOutputRoot: 'sugar_output', sugarOutputName: '',
    frameIndex: 0, objectId: 1, checkpoint: 'sam2.1_hiera_small', bboxRunner: 'auto', frameStep: preset.frameStep,
    matcher: 'sequential', sequentialOverlap: preset.sequentialOverlap, cameraModel: 'OPENCV', singleCamera: true,
    useGpu: true, useColmapMasks: false, sparseModel: '', skipFeatureExtraction: false, skipMatching: false,
    skipMapping: false, skipUndistort: false, iterations: preset.iterations, resolution: 1, eval: false, masksDir: '',
    regularization: 'dn_consistency', refinementTime: preset.sugarRefinementTime as 'short' | 'medium' | 'long',
    qualityMode: 'preset', surfaceLevel: 0.3, nVertices: null, gaussiansPerTriangle: null, refinementIterations: null,
    squareSize: 8, gpu: 0, bboxMin: '', bboxMax: '', centerBbox: true, exportObj: true, exportPly: true,
    postprocessMesh: false, postprocessDensityThreshold: 0.1, postprocessIterations: 5,
  };
}

@Injectable()
export class AdvancedPipelineFormService {
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly touchedOptions = new Set<keyof PipelineAdvancedOptions>();
  private applyingDefaults = false;
  private presets: PipelinePreset[] = [];

  readonly form = this.fb.group({
    preset: this.fb.control<PipelinePresetName>('balanced'),
    mode: this.fb.control<PipelineRunMode>('full'),
    stage: this.fb.control<PipelineStageName>('segment_video'),
    runUntil: this.fb.control<PipelineStageName>('train_3dgs'),
    stages: this.fb.control<PipelineStageName[]>(PIPELINE_STAGE_OPTIONS.slice(0, 5).map((item) => item.value)),
    options: this.fb.group(optionDefaults(FALLBACK_PRESETS.balanced)),
  });

  private readonly value = toSignal(this.form.valueChanges.pipe(map(() => this.form.getRawValue()), startWith(this.form.getRawValue())), { initialValue: this.form.getRawValue() });
  readonly mode = computed(() => this.value().mode);
  readonly selectedStages = computed(() => this.value().stages);
  readonly canSubmit = computed(() => this.mode() !== 'custom' || this.selectedStages().length > 0);
  readonly selectedStagesSummary = computed(() => this.selectedStages().length ? this.selectedStages().map((stage) => this.stageLabel(stage)).join(', ') : 'No stages selected');

  constructor() {
    for (const key of Object.keys(this.form.controls.options.controls) as (keyof PipelineAdvancedOptions)[]) {
      const control = this.form.controls.options.controls[key] as AbstractControl;
      control.valueChanges.pipe(takeUntilDestroyed()).subscribe(() => {
        if (!this.applyingDefaults) this.touchedOptions.add(key);
      });
    }
  }

  configure(presets: PipelinePreset[], selectedPreset: PipelinePresetName): void {
    this.presets = presets;
    if (this.form.controls.preset.value !== selectedPreset) this.form.controls.preset.setValue(selectedPreset, { emitEvent: false });
    this.applyPresetDefaults(selectedPreset, true);
  }

  selectPreset(preset: PipelinePresetName): void {
    this.form.controls.preset.setValue(preset);
    this.applyPresetDefaults(preset, true);
  }

  resetOptions(): void {
    this.touchedOptions.clear();
    this.applyPresetDefaults(this.form.controls.preset.value, false);
  }

  setRunUntil(stage: PipelineStageName): void {
    this.form.controls.runUntil.setValue(stage);
    const end = PIPELINE_STAGE_OPTIONS.findIndex((item) => item.value === stage);
    this.form.controls.stages.setValue(PIPELINE_STAGE_OPTIONS.slice(0, end + 1).map((item) => item.value));
  }

  toggleStage(stage: PipelineStageName, selected: boolean): void {
    const stages = new Set(this.form.controls.stages.value);
    selected ? stages.add(stage) : stages.delete(stage);
    this.form.controls.stages.setValue(PIPELINE_STAGE_OPTIONS.map((item) => item.value).filter((item) => stages.has(item)));
  }

  applyStagePreset(preset: CustomStagePreset): void {
    if (preset === 'until_3dgs') return this.setRunUntil('train_3dgs');
    this.form.controls.stages.setValue(preset === 'segmentation_prepare' ? ['segment_video', 'prepare_3dgs_dataset'] : []);
  }

  isStageSelected(stage: PipelineStageName): boolean { return this.form.controls.stages.value.includes(stage); }

  showGroup(group: AdvancedGroup): boolean {
    const mode = this.form.controls.mode.value;
    if (mode === 'full') return true;
    const stages = mode === 'custom' ? this.form.controls.stages.value : [this.form.controls.stage.value];
    if (group === 'bbox') return stages.includes('select_bbox');
    if (group === 'frames') return stages.includes('segment_video') || stages.includes('prepare_3dgs_dataset');
    if (group === 'colmap') return stages.includes('run_colmap_pipeline');
    if (group === 'gs') return stages.includes('train_3dgs') || (mode === 'stage' && (stages.includes('train_sugar') || stages.includes('sugar_metrics')));
    return stages.includes('train_sugar') || stages.includes('sugar_metrics');
  }

  buildRequest(): StartPipelineRunRequest | null {
    if (!this.canSubmit()) return null;
    const value = this.form.getRawValue();
    const options: PipelineAdvancedOptions = {};
    for (const [key, option] of Object.entries(value.options) as [keyof PipelineAdvancedOptions, PipelineAdvancedOptions[keyof PipelineAdvancedOptions]][]) {
      if (option !== '' && option !== null && option !== undefined) options[key] = option as never;
    }
    const stages = value.mode === 'custom' ? PIPELINE_STAGE_OPTIONS.map((item) => item.value).filter((stage) => value.stages.includes(stage)) : null;
    return { preset: value.preset, mode: value.mode, stage: value.mode === 'stage' ? value.stage : null, stages, options };
  }

  stageLabel(stage: string): string { return stage.replace(/_/g, ' '); }

  private applyPresetDefaults(name: PipelinePresetName, preserveTouched: boolean): void {
    const defaults = optionDefaults(this.presets.find((item) => item.name === name) ?? FALLBACK_PRESETS[name]);
    const current = this.form.controls.options.getRawValue();
    const next = { ...current };
    for (const [key, value] of Object.entries(defaults) as [keyof PipelineAdvancedOptions, PipelineAdvancedOptions[keyof PipelineAdvancedOptions]][]) {
      if (!preserveTouched || !this.touchedOptions.has(key)) next[key] = value as never;
    }
    this.applyingDefaults = true;
    this.form.controls.options.setValue(next as Required<PipelineAdvancedOptions>);
    this.applyingDefaults = false;
  }
}