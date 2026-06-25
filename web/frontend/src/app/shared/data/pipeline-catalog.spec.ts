import { buildPipelineOptionDefaults, PIPELINE_OPTIONS, PIPELINE_PRESETS, PIPELINE_STAGES, presetAsPipelinePreset } from './pipeline-catalog';

describe('pipeline catalog', () => {
  it('defines every advanced option exactly once', () => {
    const keys = PIPELINE_OPTIONS.map((option) => option.key);
    expect(new Set(keys).size).toBe(keys.length);
    expect(keys.length).toBe(47);
    expect(Object.keys(buildPipelineOptionDefaults(presetAsPipelinePreset('balanced'))).sort()).toEqual([...keys].sort());
  });

  it('keeps stages in canonical pipeline order', () => {
    expect(PIPELINE_STAGES.map((stage) => stage.name)).toEqual([
      'select_bbox', 'segment_video', 'prepare_3dgs_dataset', 'run_colmap_pipeline', 'train_3dgs', 'train_sugar', 'sugar_metrics',
    ]);
  });

  it('applies preset-dependent defaults', () => {
    const fast = buildPipelineOptionDefaults(presetAsPipelinePreset('fast'));
    const quality = buildPipelineOptionDefaults(presetAsPipelinePreset('quality'));
    expect(fast.frameStep).toBe(4);
    expect(fast.iterations).toBe(1000);
    expect(quality.frameStep).toBe(1);
    expect(quality.sequentialOverlap).toBe(40);
    expect(quality.refinementTime).toBe('long');
    expect(PIPELINE_PRESETS.fast.runSugar).toBe(false);
  });

  it('provides documentation metadata for every option', () => {
    for (const option of PIPELINE_OPTIONS) {
      expect(option.description.length).toBeGreaterThan(20);
      expect(option.effect.length).toBeGreaterThan(10);
      expect(option.documentationFragment).toMatch(/^advanced-/);
      expect(option.keywords.length).toBeGreaterThan(0);
    }
  });
});