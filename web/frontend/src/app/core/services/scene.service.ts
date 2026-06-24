import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { map, Observable } from 'rxjs';
import { SceneDto } from '../../shared/dtos/scene-data.dto';
import { Scene } from '../../shared/models/scene-data.model';
import { mapSceneDto, mapSceneDtos } from '../mappers/scene-data.mapper';

@Injectable({ providedIn: 'root' })
export class SceneService {
  private readonly http = inject(HttpClient);

  getScenes(): Observable<Scene[]> {
    return this.http.get<SceneDto[]>('/api/scenes').pipe(map(mapSceneDtos));
  }

  getSceneByName(sceneName: string): Observable<Scene> {
    return this.http.get<SceneDto>(`/api/scenes/${encodeURIComponent(sceneName)}`).pipe(map(mapSceneDto));
  }

  createScene(sceneName: string, video: File): Observable<Scene> {
    const formData = new FormData();
    formData.append('scene_name', sceneName);
    formData.append('video', video);
    return this.http.post<SceneDto>('/api/scenes', formData).pipe(map(mapSceneDto));
  }
}