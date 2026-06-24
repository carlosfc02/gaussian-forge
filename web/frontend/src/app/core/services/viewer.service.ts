import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { map, Observable } from 'rxjs';
import { ViewerLaunchDto } from '../../shared/dtos/viewer.dto';
import { ViewerLaunch } from '../../shared/models/viewer.model';
import { mapViewerLaunchDto } from '../mappers/viewer.mapper';

@Injectable({ providedIn: 'root' })
export class ViewerService {
  private readonly http = inject(HttpClient);
  launch3dgs(sceneName: string): Observable<ViewerLaunch> { return this.launch(sceneName, '3dgs'); }
  launchSugar(sceneName: string): Observable<ViewerLaunch> { return this.launch(sceneName, 'sugar'); }
  private launch(sceneName: string, viewer: '3dgs' | 'sugar'): Observable<ViewerLaunch> {
    return this.http.post<ViewerLaunchDto>(`/api/scenes/${encodeURIComponent(sceneName)}/viewers/${viewer}`, {}).pipe(map(mapViewerLaunchDto));
  }
}