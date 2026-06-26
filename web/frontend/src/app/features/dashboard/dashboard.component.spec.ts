import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { SceneService } from '../../core/services/scene.service';
import { SceneStatus } from '../../shared/models/scene-status.model';
import { DashboardComponent } from './dashboard.component';

const baseScene = {
  videoPath: 'video.mp4',
  videoUrl: '/video',
  thumbnailUrl: '/thumbnail',
  maskPaths: null,
  gsPath: null,
  sugarOutputPath: null,
  gsPlyAvailable: false,
  sugarPlyAvailable: false,
  sugarObjAvailable: false,
  pipelineRun: null,
};

describe('DashboardComponent', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('counts SuGaR ready as completed and not active', async () => {
    const sceneService = {
      getScenes: vi.fn(() => of([
        { ...baseScene, name: 'sugar', status: SceneStatus.SUGAR_READY },
        { ...baseScene, name: 'training', status: SceneStatus.TRAINING_3DGS },
      ])),
    };
    TestBed.configureTestingModule({
      imports: [DashboardComponent],
      providers: [provideRouter([]), { provide: SceneService, useValue: sceneService }],
    });

    const fixture = TestBed.createComponent(DashboardComponent);
    await vi.advanceTimersByTimeAsync(0);

    expect(fixture.componentInstance.totals().completedProjects).toBe(1);
    expect(fixture.componentInstance.totals().activeProjects).toBe(1);
  });
});
