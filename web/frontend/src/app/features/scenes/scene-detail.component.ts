import { FormsModule } from '@angular/forms';
import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ActivatedRoute } from '@angular/router';
import { toSignal } from '@angular/core/rxjs-interop';
import { NgbProgressbarModule } from '@ng-bootstrap/ng-bootstrap';
import { catchError, distinctUntilChanged, finalize, map, merge, of, Subject, switchMap, tap, timer } from 'rxjs';
import { SceneService } from '../../core/services/scene.service';
import { SceneStatusBadgeComponent } from '../../shared/components/scene-status-badge/scene-status-badge.component';
import { SceneVideoThumbnailComponent } from '../../shared/components/scene-video-thumbnail/scene-video-thumbnail.component';
import {
  PipelineAdvancedOptions,
  PipelineLog,
  PipelinePreset,
  PipelinePresetName,
  PipelineRunMode,
  PipelineStageName,
  Scene,
  StartPipelineRunRequest,
} from '../../shared/models/scene.model';
import { getSceneAssetCount, getSceneStatusMeta } from '../../shared/utils/scene-presentation';

type AdvancedOptionKey = keyof PipelineAdvancedOptions;
type AdvancedGroup = 'bbox' | 'frames' | 'colmap' | 'gs' | 'sugar';

const FALLBACK_PRESETS: Record<PipelinePresetName, PipelinePreset> = {
  fast: {
    name: 'fast',
    frameStep: 4,
    sequentialOverlap: 10,
    iterations: 1000,
    sugarMode: 'low',
    sugarRefinementTime: 'short',
  },
  balanced: {
    name: 'balanced',
    frameStep: 2,
    sequentialOverlap: 20,
    iterations: 7000,
    sugarMode: 'default',
    sugarRefinementTime: 'medium',
  },
  quality: {
    name: 'quality',
    frameStep: 1,
    sequentialOverlap: 40,
    iterations: 30000,
    sugarMode: 'high',
    sugarRefinementTime: 'long',
  },
};

function buildAdvancedDefaults(preset: PipelinePreset): PipelineAdvancedOptions {
  return {
    force: false,
    metrics: false,
    maskLoss: false,
    whiteBackground: false,
    jobPath: '',
    maskOutputDir: '',
    datasetDir: '',
    gsModelDir: '',
    sugarOutputRoot: 'sugar_output',
    sugarOutputName: '',
    frameIndex: 0,
    objectId: 1,
    checkpoint: 'sam2.1_hiera_small',
    bboxRunner: 'auto',
    frameStep: preset.frameStep,
    matcher: 'sequential',
    sequentialOverlap: preset.sequentialOverlap,
    cameraModel: 'OPENCV',
    singleCamera: true,
    useGpu: true,
    useColmapMasks: false,
    sparseModel: '',
    skipFeatureExtraction: false,
    skipMatching: false,
    skipMapping: false,
    skipUndistort: false,
    iterations: preset.iterations,
    resolution: 1,
    eval: false,
    masksDir: '',
    regularization: 'dn_consistency',
    refinementTime: preset.sugarRefinementTime as PipelineAdvancedOptions['refinementTime'],
    qualityMode: 'preset',
    surfaceLevel: 0.3,
    nVertices: null,
    gaussiansPerTriangle: null,
    refinementIterations: null,
    squareSize: 8,
    gpu: 0,
    bboxMin: '',
    bboxMax: '',
    centerBbox: true,
    exportObj: true,
    exportPly: true,
    postprocessMesh: false,
    postprocessDensityThreshold: 0.1,
    postprocessIterations: 5,
  };
}

@Component({
  selector: 'app-scene-detail',
  standalone: true,
  imports: [FormsModule, RouterLink, NgbProgressbarModule, SceneStatusBadgeComponent, SceneVideoThumbnailComponent],
  templateUrl: './scene-detail.component.html',
  styleUrl: './scene-detail.component.scss',
})
export class SceneDetailComponent {
  private readonly route = inject(ActivatedRoute);
  private readonly sceneService = inject(SceneService);
  private readonly refreshTrigger$ = new Subject<void>();
  private readonly logRefreshTrigger$ = new Subject<void>();
  private readonly advancedTouched = new Set<AdvancedOptionKey>();

  readonly pipelineStageOptions: { value: PipelineStageName; label: string }[] = [
    { value: 'select_bbox', label: 'Select bbox' },
    { value: 'segment_video', label: 'Segment video' },
    { value: 'prepare_3dgs_dataset', label: 'Prepare 3DGS dataset' },
    { value: 'run_colmap_pipeline', label: 'Run COLMAP' },
    { value: 'train_3dgs', label: 'Train 3DGS' },
    { value: 'train_sugar', label: 'Train SuGaR' },
    { value: 'sugar_metrics', label: 'SuGaR metrics' },
  ];

  readonly isLoading = signal(true);
  readonly errorMessage = signal<string | null>(null);
  readonly selectedPreset = signal<PipelinePresetName>('balanced');
  readonly advancedMode = signal<PipelineRunMode>('full');
  readonly advancedStage = signal<PipelineStageName>('segment_video');
  readonly advancedOptions = signal<PipelineAdvancedOptions>(buildAdvancedDefaults(FALLBACK_PRESETS.balanced));
  readonly isStartingPipeline = signal(false);
  readonly isStartingAdvancedPipeline = signal(false);
  readonly isCancelingPipeline = signal(false);
  readonly pipelineActionError = signal<string | null>(null);
  readonly pipelineActionMessage = signal<string | null>(null);
  readonly selectedLogStage = signal<string | null>(null);

  readonly pipelinePresets = toSignal(
    this.sceneService.getPipelinePresets().pipe(
      catchError(() => {
        this.pipelineActionError.set('Could not load pipeline presets.');
        return of([] as PipelinePreset[]);
      }),
    ),
    { initialValue: [] as PipelinePreset[] },
  );

  private readonly sceneName$ = this.route.paramMap.pipe(
    map((params) => params.get('sceneName') ?? ''),
    tap(() => {
      this.isLoading.set(true);
      this.errorMessage.set(null);
      this.pipelineActionError.set(null);
      this.pipelineActionMessage.set(null);
    }),
    distinctUntilChanged(),
  );

  private readonly scene$ = this.sceneName$.pipe(
    switchMap((sceneName) =>
      merge(timer(0, 5000), this.refreshTrigger$).pipe(
        switchMap(() =>
          this.sceneService.getSceneByName(sceneName).pipe(
            tap(() => {
              this.isLoading.set(false);
              this.errorMessage.set(null);
            }),
            catchError(() => {
              this.isLoading.set(false);
              this.errorMessage.set('Could not load live scene progress.');
              return of(null);
            }),
          ),
        ),
      ),
    ),
  );

  readonly scene = toSignal(this.scene$, { initialValue: null as Scene | null });
  readonly pipelineLog = toSignal(
    this.sceneName$.pipe(
      switchMap((sceneName) =>
        merge(timer(0, 2000), this.logRefreshTrigger$, this.refreshTrigger$).pipe(
          switchMap(() =>
            this.sceneService.getLatestPipelineLogs(sceneName, this.selectedLogStage()).pipe(
              catchError(() => of(null as PipelineLog | null)),
            ),
          ),
        ),
      ),
    ),
    { initialValue: null as PipelineLog | null },
  );

  readonly sceneMeta = computed(() => {
    const scene = this.scene();
    return scene ? getSceneStatusMeta(scene.status) : null;
  });

  readonly assetSummary = computed(() => {
    const scene = this.scene();
    return scene ? getSceneAssetCount(scene) : 0;
  });

  readonly pipelineRun = computed(() => this.scene()?.pipelineRun ?? null);

  readonly pipelineIsRunning = computed(() => this.pipelineRun()?.status === 'running');

  readonly canRunPipeline = computed(() => {
    const scene = this.scene();
    return !!scene?.videoPath && !this.pipelineIsRunning() && !this.isStartingPipeline() && !this.isStartingAdvancedPipeline() && !this.isCancelingPipeline();
  });

  setSelectedPreset(preset: PipelinePresetName): void {
    this.selectedPreset.set(preset);
    const defaults = buildAdvancedDefaults(this.getPresetConfig(preset));
    this.advancedOptions.update((options) => {
      const next = { ...options };
      for (const [key, value] of Object.entries(defaults) as [AdvancedOptionKey, PipelineAdvancedOptions[AdvancedOptionKey]][]) {
        if (!this.advancedTouched.has(key)) {
          next[key] = value as never;
        }
      }
      return next;
    });
  }

  setAdvancedMode(mode: PipelineRunMode): void {
    this.advancedMode.set(mode);
  }

  setAdvancedStage(stage: PipelineStageName): void {
    this.advancedStage.set(stage);
  }

  setAdvancedTextOption(key: AdvancedOptionKey, value: string): void {
    this.advancedTouched.add(key);
    this.advancedOptions.update((options) => ({ ...options, [key]: value }));
  }

  setAdvancedNumberOption(key: AdvancedOptionKey, value: number | string | null): void {
    this.advancedTouched.add(key);
    const numericValue = typeof value === 'number' ? value : Number(value);
    this.advancedOptions.update((options) => ({
      ...options,
      [key]: Number.isFinite(numericValue) ? numericValue : null,
    }));
  }

  setAdvancedBooleanOption(key: AdvancedOptionKey, value: boolean): void {
    this.advancedTouched.add(key);
    this.advancedOptions.update((options) => ({ ...options, [key]: value }));
  }

  resetAdvancedOptions(): void {
    this.advancedTouched.clear();
    this.advancedOptions.set(buildAdvancedDefaults(this.getPresetConfig(this.selectedPreset())));
  }

  setSelectedLogStage(stage: string): void {
    this.selectedLogStage.set(stage || null);
    this.logRefreshTrigger$.next();
  }

  startPipeline(): void {
    const scene = this.scene();
    if (!scene || !this.canRunPipeline()) {
      return;
    }

    this.isStartingPipeline.set(true);
    this.pipelineActionError.set(null);
    this.pipelineActionMessage.set(null);

    this.sceneService
      .startPipelineRun(scene.name, this.selectedPreset())
      .pipe(finalize(() => this.isStartingPipeline.set(false)))
      .subscribe({
        next: (run) => {
          this.pipelineActionMessage.set(`Pipeline run ${run.runName} started.`);
          this.refreshTrigger$.next();
          this.logRefreshTrigger$.next();
        },
        error: (error) => {
          this.pipelineActionError.set(
            error?.error?.detail ?? 'Could not start the full pipeline. Check the backend logs.',
          );
        },
      });
  }

  startAdvancedPipeline(): void {
    const scene = this.scene();
    if (!scene || !this.canRunPipeline()) {
      return;
    }

    const request: StartPipelineRunRequest = {
      preset: this.selectedPreset(),
      mode: this.advancedMode(),
      stage: this.advancedMode() === 'stage' ? this.advancedStage() : null,
      options: this.cleanAdvancedOptions(this.advancedOptions()),
    };

    this.isStartingAdvancedPipeline.set(true);
    this.pipelineActionError.set(null);
    this.pipelineActionMessage.set(null);

    this.sceneService
      .startPipelineRun(scene.name, request)
      .pipe(finalize(() => this.isStartingAdvancedPipeline.set(false)))
      .subscribe({
        next: (run) => {
          this.pipelineActionMessage.set(`Advanced pipeline run ${run.runName} started.`);
          this.refreshTrigger$.next();
          this.logRefreshTrigger$.next();
        },
        error: (error) => {
          this.pipelineActionError.set(
            error?.error?.detail ?? 'Could not start the advanced pipeline. Check the backend logs.',
          );
        },
      });
  }

  cancelPipeline(): void {
    const scene = this.scene();
    if (!scene || !this.pipelineIsRunning() || this.isCancelingPipeline()) {
      return;
    }

    this.isCancelingPipeline.set(true);
    this.pipelineActionError.set(null);
    this.pipelineActionMessage.set(null);

    this.sceneService
      .cancelPipelineRun(scene.name)
      .pipe(finalize(() => this.isCancelingPipeline.set(false)))
      .subscribe({
        next: () => {
          this.pipelineActionMessage.set('Pipeline run canceled.');
          this.refreshTrigger$.next();
          this.logRefreshTrigger$.next();
        },
        error: (error) => {
          this.pipelineActionError.set(
            error?.error?.detail ?? 'Could not cancel the pipeline. Check the backend logs.',
          );
        },
      });
  }

  showAdvancedGroup(group: AdvancedGroup): boolean {
    if (this.advancedMode() === 'full') {
      return true;
    }

    const stage = this.advancedStage();
    if (group === 'bbox') {
      return stage === 'select_bbox';
    }
    if (group === 'frames') {
      return stage === 'segment_video' || stage === 'prepare_3dgs_dataset';
    }
    if (group === 'colmap') {
      return stage === 'run_colmap_pipeline';
    }
    if (group === 'gs') {
      return stage === 'train_3dgs' || stage === 'train_sugar' || stage === 'sugar_metrics';
    }
    return stage === 'train_sugar' || stage === 'sugar_metrics';
  }

  getStageLabel(stage: string | null): string {
    if (!stage) {
      return 'Active stage';
    }

    return stage.replace(/_/g, ' ');
  }

  getPresetLabel(preset: PipelinePresetName): string {
    return preset.charAt(0).toUpperCase() + preset.slice(1);
  }

  getPresetSummary(preset: PipelinePreset): string {
    return `${preset.iterations.toLocaleString()} iterations, frames every ${preset.frameStep}, ${preset.sugarRefinementTime} SuGaR`;
  }

  private getPresetConfig(preset: PipelinePresetName): PipelinePreset {
    return this.pipelinePresets().find((candidate) => candidate.name === preset) ?? FALLBACK_PRESETS[preset];
  }

  private cleanAdvancedOptions(options: PipelineAdvancedOptions): PipelineAdvancedOptions {
    const cleaned: PipelineAdvancedOptions = {};
    for (const [key, value] of Object.entries(options) as [AdvancedOptionKey, PipelineAdvancedOptions[AdvancedOptionKey]][]) {
      if (value === '' || value === null || value === undefined) {
        continue;
      }
      cleaned[key] = value as never;
    }
    return cleaned;
  }
}
