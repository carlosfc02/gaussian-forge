import { TestBed } from '@angular/core/testing';
import { ActivatedRoute, convertToParamMap } from '@angular/router';
import { BehaviorSubject, of } from 'rxjs';
import { PipelineService } from '../../../core/services/pipeline.service';
import { SceneMetricsService } from '../../../core/services/scene-metrics.service';
import { SceneService } from '../../../core/services/scene.service';
import { ViewerService } from '../../../core/services/viewer.service';
import { SceneStatus } from '../../../shared/models/scene-status.model';
import { SceneDetailFacade } from './scene-detail.facade';

describe('SceneDetailFacade', () => {
  const params = new BehaviorSubject(convertToParamMap({ sceneName: 'scene' }));
  const scene = { name: 'scene', status: SceneStatus.VIDEO_UPLOADED, videoPath: 'video.mp4', videoUrl: '/video', thumbnailUrl: '/thumb', maskPaths: null, gsPath: null, sugarOutputPath: null, pipelineRun: null };
  const run = { sceneName: 'scene', runName: 'run', preset: 'balanced', status: 'running', mode: 'full', stage: null, stages: null, options: null, startedAt: null, finishedAt: null, currentStage: null, manifestPath: null, error: null };
  let sceneService: any; let pipelineService: any; let metricsService: any; let viewerService: any;

  beforeEach(() => {
    vi.useFakeTimers();
    sceneService = { getSceneByName: vi.fn(() => of(scene)) };
    pipelineService = { getPresets: vi.fn(() => of([])), getLatestLogs: vi.fn(() => of(null)), start: vi.fn(() => of(run)), cancel: vi.fn(() => of({ ...run, status: 'canceled' })) };
    metricsService = { get: vi.fn(() => of({ sceneName: 'scene', stages: [], updatedAt: null })) };
    viewerService = { launch3dgs: vi.fn(() => of({ message: 'Opening' })), launchSugar: vi.fn(() => of({ message: 'Opening' })) };
    TestBed.configureTestingModule({ providers: [SceneDetailFacade, { provide: ActivatedRoute, useValue: { paramMap: params.asObservable() } }, { provide: SceneService, useValue: sceneService }, { provide: PipelineService, useValue: pipelineService }, { provide: SceneMetricsService, useValue: metricsService }, { provide: ViewerService, useValue: viewerService }] });
  });

  afterEach(() => vi.useRealTimers());

  it('polls scene, metrics and logs at their configured intervals', async () => {
    const facade = TestBed.inject(SceneDetailFacade);
    await vi.advanceTimersByTimeAsync(0);
    expect(facade.scene()?.name).toBe('scene');
    expect(sceneService.getSceneByName).toHaveBeenCalledTimes(1);
    expect(metricsService.get).toHaveBeenCalledTimes(1);
    expect(pipelineService.getLatestLogs).toHaveBeenCalledTimes(1);
    expect(pipelineService.getLatestLogs).toHaveBeenLastCalledWith('scene', null);
    await vi.advanceTimersByTimeAsync(2000);
    expect(pipelineService.getLatestLogs).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(3000);
    expect(sceneService.getSceneByName).toHaveBeenCalledTimes(2);
    expect(metricsService.get).toHaveBeenCalledTimes(2);
  });

  it('refreshes scene and logs after starting a run', async () => {
    const facade = TestBed.inject(SceneDetailFacade);
    await vi.advanceTimersByTimeAsync(0);
    facade.startSimplePipeline();
    expect(pipelineService.start).toHaveBeenCalledWith('scene', 'balanced');
    expect(sceneService.getSceneByName).toHaveBeenCalledTimes(2);
    expect(pipelineService.getLatestLogs).toHaveBeenCalledTimes(3);
    expect(facade.pipelineActionMessage()).toContain('run');
  });

  it('requests a selected log stage immediately', async () => {
    const facade = TestBed.inject(SceneDetailFacade);
    await vi.advanceTimersByTimeAsync(0);
    facade.setSelectedLogStage('train_3dgs');
    expect(pipelineService.getLatestLogs).toHaveBeenLastCalledWith('scene', 'train_3dgs');
  });
});