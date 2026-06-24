import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { map, Observable } from 'rxjs';
import { SceneMetricsDto } from '../../shared/dtos/metrics.dto';
import { SceneMetrics } from '../../shared/models/metrics.model';
import { mapSceneMetricsDto } from '../mappers/metrics.mapper';

@Injectable({ providedIn: 'root' })
export class SceneMetricsService {
  private readonly http = inject(HttpClient);
  get(sceneName: string): Observable<SceneMetrics> {
    return this.http.get<SceneMetricsDto>(`/api/scenes/${encodeURIComponent(sceneName)}/metrics`).pipe(map(mapSceneMetricsDto));
  }
}