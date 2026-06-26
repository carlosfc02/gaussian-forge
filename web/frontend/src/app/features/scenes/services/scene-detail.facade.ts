import { computed, inject, Injectable, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute } from '@angular/router';
import { catchError, distinctUntilChanged, finalize, map, merge, of, shareReplay, Subject, switchMap, tap, timer } from 'rxjs';
import { PipelineService } from '../../../core/services/pipeline.service';
import { SceneAssetKind, SceneAssetService } from '../../../core/services/scene-asset.service';
import { SceneMetricsService } from '../../../core/services/scene-metrics.service';
import { SceneService } from '../../../core/services/scene.service';
import { ViewerService } from '../../../core/services/viewer.service';
import { PipelineLog, PipelinePreset, PipelinePresetName, StartPipelineRunRequest } from '../../../shared/models/pipeline.model';
import { Scene } from '../../../shared/models/scene-data.model';
import { getSceneAssetCount, getSceneStatusMeta } from '../../../shared/utils/scene-presentation';

@Injectable()
export class SceneDetailFacade {
  private readonly route = inject(ActivatedRoute);
  private readonly sceneService = inject(SceneService);
  private readonly sceneAssetService = inject(SceneAssetService);
  private readonly pipelineService = inject(PipelineService);
  private readonly metricsService = inject(SceneMetricsService);
  private readonly viewerService = inject(ViewerService);
  private readonly refreshTrigger$ = new Subject<void>();
  private readonly logRefreshTrigger$ = new Subject<void>();

  readonly isLoading = signal(true);
  readonly errorMessage = signal<string | null>(null);
  readonly selectedPreset = signal<PipelinePresetName>('balanced');
  readonly selectedLogStage = signal<string | null>(null);
  readonly isStartingPipeline = signal(false);
  readonly isStartingAdvancedPipeline = signal(false);
  readonly isCancelingPipeline = signal(false);
  readonly pipelineActionError = signal<string | null>(null);
  readonly pipelineActionMessage = signal<string | null>(null);
  readonly viewerActionError = signal<string | null>(null);
  readonly viewerActionMessage = signal<string | null>(null);
  readonly isLaunching3dgsViewer = signal(false);
  readonly isLaunchingSugarViewer = signal(false);
  readonly downloadingAsset = signal<SceneAssetKind | null>(null);
  readonly assetActionError = signal<string | null>(null);
  readonly assetActionMessage = signal<string | null>(null);
  readonly isClearingGeneratedData = signal(false);
  readonly clearActionError = signal<string | null>(null);
  readonly clearActionMessage = signal<string | null>(null);

  private readonly sceneName$ = this.route.paramMap.pipe(
    map((params) => params.get('sceneName') ?? ''),
    distinctUntilChanged(),
    tap(() => this.resetRouteState()),
    shareReplay({ bufferSize: 1, refCount: true }),
  );

  readonly scene = toSignal(
    this.sceneName$.pipe(
      switchMap((sceneName) => merge(timer(0, 5000), this.refreshTrigger$).pipe(
        switchMap(() => this.sceneService.getSceneByName(sceneName).pipe(
          tap(() => { this.isLoading.set(false); this.errorMessage.set(null); }),
          catchError(() => { this.isLoading.set(false); this.errorMessage.set('Could not load live scene progress.'); return of(null as Scene | null); }),
        )),
      )),
    ),
    { initialValue: null as Scene | null },
  );

  readonly pipelineLog = toSignal(
    this.sceneName$.pipe(
      switchMap((sceneName) => merge(timer(0, 2000), this.logRefreshTrigger$, this.refreshTrigger$).pipe(
        switchMap(() => this.pipelineService.getLatestLogs(sceneName, this.selectedLogStage()).pipe(
          catchError(() => of(null as PipelineLog | null)),
        )),
      )),
    ),
    { initialValue: null as PipelineLog | null },
  );

  readonly sceneMetrics = toSignal(
    this.sceneName$.pipe(
      switchMap((sceneName) => merge(timer(0, 5000), this.refreshTrigger$).pipe(
        switchMap(() => this.metricsService.get(sceneName).pipe(catchError(() => of(null)))),
      )),
    ),
    { initialValue: null },
  );

  readonly pipelinePresets = toSignal(
    this.pipelineService.getPresets().pipe(
      catchError(() => { this.pipelineActionError.set('Could not load pipeline presets.'); return of([] as PipelinePreset[]); }),
    ),
    { initialValue: [] as PipelinePreset[] },
  );

  readonly sceneMeta = computed(() => this.scene() ? getSceneStatusMeta(this.scene()!.status) : null);
  readonly assetSummary = computed(() => this.scene() ? getSceneAssetCount(this.scene()!) : 0);
  readonly pipelineRun = computed(() => this.scene()?.pipelineRun ?? null);
  readonly metricStages = computed(() => this.sceneMetrics()?.stages ?? []);
  readonly pipelineIsRunning = computed(() => this.pipelineRun()?.status === 'running');
  readonly canRunPipeline = computed(() => !!this.scene()?.videoPath && !this.pipelineIsRunning() && !this.isStartingPipeline() && !this.isStartingAdvancedPipeline() && !this.isCancelingPipeline());
  readonly canClearGeneratedData = computed(() => !!this.scene()?.videoPath && !this.pipelineIsRunning() && !this.isClearingGeneratedData());

  setSelectedPreset(preset: PipelinePresetName): void { this.selectedPreset.set(preset); }
  setSelectedLogStage(stage: string): void { this.selectedLogStage.set(stage || null); this.logRefreshTrigger$.next(); }

  startSimplePipeline(): void {
    const scene = this.scene();
    if (!scene || !this.canRunPipeline()) return;
    this.isStartingPipeline.set(true);
    this.clearPipelineMessages();
    this.pipelineService.start(scene.name, this.selectedPreset()).pipe(finalize(() => this.isStartingPipeline.set(false))).subscribe({
      next: (run) => { this.pipelineActionMessage.set(`Pipeline run ${run.runName} started.`); this.refresh(); },
      error: (error) => this.pipelineActionError.set(error?.error?.detail ?? 'Could not start the full pipeline. Check the backend logs.'),
    });
  }

  startAdvancedPipeline(request: StartPipelineRunRequest): void {
    const scene = this.scene();
    if (!scene || !this.canRunPipeline()) return;
    this.isStartingAdvancedPipeline.set(true);
    this.clearPipelineMessages();
    this.pipelineService.start(scene.name, request).pipe(finalize(() => this.isStartingAdvancedPipeline.set(false))).subscribe({
      next: (run) => { this.pipelineActionMessage.set(`Advanced pipeline run ${run.runName} started.`); this.refresh(); },
      error: (error) => this.pipelineActionError.set(error?.error?.detail ?? 'Could not start the advanced pipeline. Check the backend logs.'),
    });
  }

  cancelPipeline(): void {
    const scene = this.scene();
    if (!scene || !this.pipelineIsRunning() || this.isCancelingPipeline()) return;
    this.isCancelingPipeline.set(true);
    this.clearPipelineMessages();
    this.pipelineService.cancel(scene.name).pipe(finalize(() => this.isCancelingPipeline.set(false))).subscribe({
      next: () => { this.pipelineActionMessage.set('Pipeline run canceled.'); this.refresh(); },
      error: (error) => this.pipelineActionError.set(error?.error?.detail ?? 'Could not cancel the pipeline. Check the backend logs.'),
    });
  }

  launch3dgsViewer(): void { this.launchViewer('3dgs'); }
  launchSugarViewer(): void { this.launchViewer('sugar'); }
  download3dgsPly(): void { this.downloadAsset('3dgs-ply'); }
  downloadSugarPly(): void { this.downloadAsset('sugar-ply'); }
  downloadSugarObj(): void { this.downloadAsset('sugar-obj'); }

  clearGeneratedData(): void {
    const scene = this.scene();
    if (!scene || !this.canClearGeneratedData()) return;

    this.isClearingGeneratedData.set(true);
    this.clearActionError.set(null);
    this.clearActionMessage.set(null);
    this.sceneService.clearGeneratedData(scene.name).pipe(
      finalize(() => this.isClearingGeneratedData.set(false)),
    ).subscribe({
      next: () => {
        this.clearActionMessage.set('Generated data cleared. The original video and GT data were kept.');
        this.selectedLogStage.set(null);
        this.refresh();
      },
      error: (error) => this.clearActionError.set(
        error?.error?.detail ?? 'Could not clear the generated scene data.',
      ),
    });
  }

  private downloadAsset(asset: SceneAssetKind): void {
    const scene = this.scene();
    if (!scene || this.downloadingAsset() !== null) return;

    this.downloadingAsset.set(asset);
    this.assetActionError.set(null);
    this.assetActionMessage.set(null);
    this.sceneAssetService.download(scene.name, asset).pipe(
      finalize(() => this.downloadingAsset.set(null)),
    ).subscribe({
      next: (filename) => this.assetActionMessage.set(`${filename} downloaded.`),
      error: (error) => this.assetActionError.set(
        error?.error?.detail ?? 'Could not download the requested model.',
      ),
    });
  }

  private launchViewer(viewer: '3dgs' | 'sugar'): void {
    const scene = this.scene();
    const running = viewer === '3dgs' ? this.isLaunching3dgsViewer : this.isLaunchingSugarViewer;
    if (!scene || running()) return;
    running.set(true);
    this.viewerActionError.set(null);
    this.viewerActionMessage.set(null);
    const request = viewer === '3dgs' ? this.viewerService.launch3dgs(scene.name) : this.viewerService.launchSugar(scene.name);
    request.pipe(finalize(() => running.set(false))).subscribe({
      next: (launch) => this.viewerActionMessage.set(launch.message),
      error: (error) => this.viewerActionError.set(error?.error?.detail ?? `Could not launch the ${viewer === '3dgs' ? '3DGS' : 'SuGaR'} viewer.`),
    });
  }

  private refresh(): void { this.refreshTrigger$.next(); this.logRefreshTrigger$.next(); }
  private clearPipelineMessages(): void { this.pipelineActionError.set(null); this.pipelineActionMessage.set(null); }
  private resetRouteState(): void {
    this.isLoading.set(true);
    this.errorMessage.set(null);
    this.clearPipelineMessages();
    this.viewerActionError.set(null);
    this.viewerActionMessage.set(null);
    this.assetActionError.set(null);
    this.assetActionMessage.set(null);
    this.clearActionError.set(null);
    this.clearActionMessage.set(null);
    this.selectedLogStage.set(null);
  }
}
