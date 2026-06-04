import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ActivatedRoute } from '@angular/router';
import { toSignal } from '@angular/core/rxjs-interop';
import { NgbProgressbarModule } from '@ng-bootstrap/ng-bootstrap';
import { catchError, distinctUntilChanged, map, of, switchMap, tap, timer } from 'rxjs';
import { SceneService } from '../../core/services/scene.service';
import { SceneStatusBadgeComponent } from '../../shared/components/scene-status-badge/scene-status-badge.component';
import { SceneVideoThumbnailComponent } from '../../shared/components/scene-video-thumbnail/scene-video-thumbnail.component';
import { Scene } from '../../shared/models/scene.model';
import { getSceneAssetCount, getSceneStatusMeta } from '../../shared/utils/scene-presentation';

@Component({
  selector: 'app-scene-detail',
  standalone: true,
  imports: [RouterLink, NgbProgressbarModule, SceneStatusBadgeComponent, SceneVideoThumbnailComponent],
  templateUrl: './scene-detail.component.html',
  styleUrl: './scene-detail.component.scss',
})
export class SceneDetailComponent {
  private readonly route = inject(ActivatedRoute);
  private readonly sceneService = inject(SceneService);

  readonly isLoading = signal(true);
  readonly errorMessage = signal<string | null>(null);

  private readonly sceneName$ = this.route.paramMap.pipe(
    map((params) => params.get('sceneName') ?? ''),
    tap(() => {
      this.isLoading.set(true);
      this.errorMessage.set(null);
    }),
    distinctUntilChanged(),
  );

  private readonly scene$ = this.sceneName$.pipe(
    switchMap((sceneName) =>
      timer(0, 5000).pipe(
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

  readonly sceneMeta = computed(() => {
    const scene = this.scene();
    return scene ? getSceneStatusMeta(scene.status) : null;
  });

  readonly assetSummary = computed(() => {
    const scene = this.scene();
    return scene ? getSceneAssetCount(scene) : 0;
  });
}
