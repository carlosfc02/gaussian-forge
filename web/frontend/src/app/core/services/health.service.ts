import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { map, Observable } from 'rxjs';

import { API_PATHS } from '../api/api-paths';
import { HealthInfo } from '../../shared/models/health-info.interface';
import { HealthResponse } from '../../shared/models/healthResponse.interface';

@Injectable({
  providedIn: 'root',
})
export class HealthService {
  private readonly http = inject(HttpClient);

  getHealth(): Observable<HealthInfo> {
    return this.http.get<HealthResponse>(API_PATHS.health).pipe(
      map((response): HealthInfo => ({
        status: response.status,
        projectRoot: response.project_root,
        videosDir: response.videos_dir,
        scriptsDir: response.scripts_dir,
      })),
    );
  }
}
