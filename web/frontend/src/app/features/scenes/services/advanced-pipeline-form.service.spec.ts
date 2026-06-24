import { TestBed } from '@angular/core/testing';
import { AdvancedPipelineFormService, FALLBACK_PRESETS } from './advanced-pipeline-form.service';

describe('AdvancedPipelineFormService', () => {
  let service: AdvancedPipelineFormService;
  beforeEach(() => { TestBed.configureTestingModule({ providers: [AdvancedPipelineFormService] }); service = TestBed.inject(AdvancedPipelineFormService); service.configure(Object.values(FALLBACK_PRESETS), 'balanced'); });

  it('applies preset defaults', () => { service.selectPreset('fast'); expect(service.form.controls.options.controls.frameStep.value).toBe(4); expect(service.form.controls.options.controls.iterations.value).toBe(1000); });
  it('preserves manual overrides when the preset changes', () => { service.form.controls.options.controls.frameStep.setValue(9); service.selectPreset('quality'); expect(service.form.controls.options.controls.frameStep.value).toBe(9); expect(service.form.controls.options.controls.iterations.value).toBe(30000); });
  it('builds custom stages in canonical order', () => { service.form.controls.mode.setValue('custom'); service.form.controls.stages.setValue(['train_3dgs', 'segment_video']); const request = service.buildRequest(); expect(request?.stages).toEqual(['segment_video', 'train_3dgs']); service.toggleStage('prepare_3dgs_dataset', true); expect(service.form.controls.stages.value).toEqual(['segment_video', 'prepare_3dgs_dataset', 'train_3dgs']); });
  it('rejects a custom run without stages', () => { service.form.controls.mode.setValue('custom'); service.applyStagePreset('clear'); expect(service.canSubmit()).toBe(false); expect(service.buildRequest()).toBeNull(); });
  it('shows options only for selected custom stages', () => { service.form.controls.mode.setValue('custom'); service.form.controls.stages.setValue(['segment_video', 'prepare_3dgs_dataset']); expect(service.showGroup('frames')).toBe(true); expect(service.showGroup('gs')).toBe(false); expect(service.showGroup('sugar')).toBe(false); });
});