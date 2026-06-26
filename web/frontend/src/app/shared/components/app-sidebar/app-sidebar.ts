import { Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { NgbTooltip } from '@ng-bootstrap/ng-bootstrap';
import { catchError, map, of, switchMap, timeout, timer } from 'rxjs';
import { HealthService } from '../../../core/services/health.service';

export type BackendConnectionStatus = 'checking' | 'connected' | 'disconnected';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, NgbTooltip],
  templateUrl: './app-sidebar.html',
  styleUrls: ['./app-sidebar.scss'],
})
export class AppSidebarComponent {
  private readonly healthService = inject(HealthService);

  readonly backendStatus = toSignal(
    timer(0, 5000).pipe(
      switchMap(() =>
        this.healthService.getHealth().pipe(
          timeout({ first: 3000 }),
          map((health): BackendConnectionStatus =>
            health.status === 'ok' ? 'connected' : 'disconnected',
          ),
          catchError(() => of<BackendConnectionStatus>('disconnected')),
        ),
      ),
    ),
    { initialValue: 'checking' as BackendConnectionStatus },
  );

  readonly backendStatusLabel = computed(() => {
    switch (this.backendStatus()) {
      case 'connected':
        return 'Backend connected';
      case 'disconnected':
        return 'Backend disconnected';
      default:
        return 'Checking backend connection';
    }
  });
}
