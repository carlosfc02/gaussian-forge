import { FormsModule } from '@angular/forms';
import { Component, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { toSignal } from '@angular/core/rxjs-interop';
import { NgbProgressbarModule } from '@ng-bootstrap/ng-bootstrap';
import { catchError, merge, of, Subject, switchMap, tap, timer } from 'rxjs';
import { SceneService } from '../../core/services/scene.service';
import { ScenesListComponent } from '../scenes/components/scenes-list/scenes-list.component';
import { Scene } from '../../shared/models/scene.model';
import {
  getSceneStatusMeta,
  isSceneHealthy,
  isSceneTerminal,
} from '../../shared/utils/scene-presentation';
import { SceneStatusBadgeComponent } from '../../shared/components/scene-status-badge/scene-status-badge.component';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    FormsModule,
    RouterLink,
    NgbProgressbarModule,
    ScenesListComponent,
    SceneStatusBadgeComponent,
  ],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
})
export class DashboardComponent {
  private readonly sceneService = inject(SceneService);
  private readonly refreshTrigger$ = new Subject<void>();

  readonly searchTerm = signal('');
  readonly isLoading = signal(true);
  readonly errorMessage = signal<string | null>(null);

  private readonly scenes$ = merge(timer(0, 8000), this.refreshTrigger$).pipe(
    switchMap(() =>
      this.sceneService.getScenes().pipe(
        tap(() => {
          this.isLoading.set(false);
          this.errorMessage.set(null);
        }),
        catchError(() => {
          this.isLoading.set(false);
          this.errorMessage.set('Could not load project telemetry from the API.');
          return of([] as Scene[]);
        }),
      ),
    ),
  );

  readonly scenes = toSignal(this.scenes$, { initialValue: [] as Scene[] });

  readonly filteredScenes = computed(() => {
    const query = this.searchTerm().trim().toLowerCase();
    if (!query) {
      return this.scenes();
    }

    return this.scenes().filter((scene) => {
      const meta = getSceneStatusMeta(scene.status);
      return [scene.name, meta.label, meta.stage, meta.description].some((value) =>
        value.toLowerCase().includes(query),
      );
    });
  });

  readonly activeScene = computed(() => {
    return (
      [...this.scenes()]
        .filter((scene) => !isSceneTerminal(scene.status))
        .sort((left, right) => getSceneStatusMeta(right.status).progress - getSceneStatusMeta(left.status).progress)[0] ??
      this.scenes()[0] ??
      null
    );
  });

  readonly totals = computed(() => {
    const scenes = this.scenes();
    const totalProjects = scenes.length;
    const activeProjects = scenes.filter((scene) => !isSceneTerminal(scene.status)).length;
    const completedProjects = scenes.filter(
      (scene) =>
        isSceneHealthy(scene.status) && getSceneStatusMeta(scene.status).progress >= 99,
    ).length;
    const healthyProjects = scenes.filter((scene) => isSceneHealthy(scene.status)).length;
    const averageCompletion = totalProjects
      ? Math.round(
          scenes.reduce((sum, scene) => sum + getSceneStatusMeta(scene.status).progress, 0) / totalProjects,
        )
      : 0;

    return {
      totalProjects,
      activeProjects,
      completedProjects,
      healthyProjects,
      averageCompletion,
    };
  });

  readonly emptyTitle = computed(() =>
    this.searchTerm().trim() ? 'No projects match this search' : 'No projects yet',
  );

  readonly emptyDescription = computed(() =>
    this.searchTerm().trim()
      ? 'Try another keyword or clear the filter to see all reconstruction scenes.'
      : 'Create your first reconstruction project to start the pipeline.',
  );

  refreshScenes(): void {
    this.isLoading.set(true);
    this.refreshTrigger$.next();
  }

  getSceneStage(scene: Scene): string {
    return getSceneStatusMeta(scene.status).stage;
  }

  getSceneProgress(scene: Scene): number {
    return getSceneStatusMeta(scene.status).progress;
  }
}
