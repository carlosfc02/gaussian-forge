import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { PipelineService } from './pipeline.service';

describe('PipelineService', () => {
  let service: PipelineService; let http: HttpTestingController;
  beforeEach(() => { TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] }); service = TestBed.inject(PipelineService); http = TestBed.inject(HttpTestingController); });
  afterEach(() => http.verify());
  it('loads and maps presets', () => { let value: any; service.getPresets().subscribe((result) => value = result[0]); const request = http.expectOne('/api/pipeline/presets'); expect(request.request.method).toBe('GET'); request.flush([{ name: 'fast', frame_step: 4, sequential_overlap: 10, iterations: 1000, sugar_mode: 'low', sugar_refinement_time: 'short', run_sugar: false }]); expect(value).toMatchObject({ name: 'fast', frameStep: 4, runSugar: false }); });
  it('starts a custom run with the unchanged backend payload', () => { service.start('my scene', { preset: 'fast', mode: 'custom', stages: ['segment_video'] }).subscribe(); const request = http.expectOne('/api/scenes/my%20scene/pipeline-runs'); expect(request.request.method).toBe('POST'); expect(request.request.body).toEqual({ preset: 'fast', mode: 'custom', stages: ['segment_video'] }); request.flush({ scene_name: 'my scene', run_name: 'run', preset: 'fast', status: 'running', mode: 'custom', stage: null, stages: ['segment_video'], options: null, started_at: null, finished_at: null, current_stage: null, manifest_path: null, error: null }); });
  it('requests the selected live log stage', () => { service.getLatestLogs('scene', 'train_3dgs').subscribe(); const request = http.expectOne('/api/scenes/scene/pipeline-runs/latest/logs?stage=train_3dgs'); expect(request.request.method).toBe('GET'); request.flush(null); });
});