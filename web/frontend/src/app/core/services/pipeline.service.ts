import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { map, Observable } from 'rxjs';
import { PipelineLogDto, PipelinePresetDto, PipelineRunDto } from '../../shared/dtos/pipeline.dto';
import { PipelineLog, PipelinePreset, PipelinePresetName, PipelineRun, StartPipelineRunRequest } from '../../shared/models/pipeline.model';
import { mapPipelineLogDto, mapPipelinePresetDto, mapPipelineRunDto } from '../mappers/pipeline.mapper';

@Injectable({ providedIn: 'root' })
export class PipelineService {
  private readonly http = inject(HttpClient);

  getPresets(): Observable<PipelinePreset[]> {
    return this.http.get<PipelinePresetDto[]>('/api/pipeline/presets').pipe(map((items) => items.map(mapPipelinePresetDto)));
  }

  start(sceneName: string, request: PipelinePresetName | StartPipelineRunRequest): Observable<PipelineRun> {
    const body = typeof request === 'string' ? { preset: request } : request;
    return this.http.post<PipelineRunDto>(`/api/scenes/${encodeURIComponent(sceneName)}/pipeline-runs`, body).pipe(map(mapPipelineRunDto));
  }

  cancel(sceneName: string): Observable<PipelineRun> {
    return this.http.post<PipelineRunDto>(`/api/scenes/${encodeURIComponent(sceneName)}/pipeline-runs/latest/cancel`, {}).pipe(map(mapPipelineRunDto));
  }

  getLatestRun(sceneName: string): Observable<PipelineRun | null> {
    return this.http.get<PipelineRunDto | null>(`/api/scenes/${encodeURIComponent(sceneName)}/pipeline-runs/latest`).pipe(map((run) => run ? mapPipelineRunDto(run) : null));
  }

  getLatestLogs(sceneName: string, stage: string | null = null): Observable<PipelineLog | null> {
    const query = stage ? `?stage=${encodeURIComponent(stage)}` : '';
    return this.http.get<PipelineLogDto | null>(`/api/scenes/${encodeURIComponent(sceneName)}/pipeline-runs/latest/logs${query}`).pipe(map((log) => log ? mapPipelineLogDto(log) : null));
  }
}