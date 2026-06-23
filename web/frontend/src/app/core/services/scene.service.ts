import { HttpClient } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { map, Observable } from 'rxjs';

import { PipelineLog, PipelinePreset, PipelinePresetName, PipelineRun, Scene, StartPipelineRunRequest } from '../../shared/models/scene.model';
import { PipelineLogDto, PipelinePresetDto, PipelineRunDto, SceneDto } from '../../shared/dtos/scene.dto';
import {
    mapPipelineLogDtoToPipelineLog,
    mapPipelinePresetDtoToPipelinePreset,
    mapPipelineRunDtoToPipelineRun,
    mapSceneDtosToScene,
    mapSceneDtoToScene,
} from '../mappers/scene.mapper';


@Injectable({
    providedIn: 'root'
})
export class SceneService {
    private readonly http = inject(HttpClient);

    getScenes(): Observable<Scene[]> {
        return this.http.get<SceneDto[]>('/api/scenes')
        .pipe(map(mapSceneDtosToScene));
    }

    getSceneByName(sceneName: string): Observable<Scene> {
        const encodedSceneName = encodeURIComponent(sceneName);

        return this.http.get<SceneDto>(`/api/scenes/${encodedSceneName}`)
        .pipe(map(mapSceneDtoToScene));
    }

    createScene(sceneName: string, video: File): Observable<Scene> {
        const formData = new FormData();

        formData.append('scene_name', sceneName);
        formData.append('video', video);

        return this.http.post<SceneDto>('/api/scenes', formData).pipe(map(mapSceneDtoToScene))
    }

    getPipelinePresets(): Observable<PipelinePreset[]> {
        return this.http.get<PipelinePresetDto[]>('/api/pipeline/presets')
        .pipe(map((presets) => presets.map(mapPipelinePresetDtoToPipelinePreset)));
    }

    startPipelineRun(sceneName: string, request: PipelinePresetName | StartPipelineRunRequest): Observable<PipelineRun> {
        const body = typeof request === 'string' ? { preset: request } : request;
        const encodedSceneName = encodeURIComponent(sceneName);

        return this.http.post<PipelineRunDto>(`/api/scenes/${encodedSceneName}/pipeline-runs`, body)
        .pipe(map(mapPipelineRunDtoToPipelineRun));
    }

    cancelPipelineRun(sceneName: string): Observable<PipelineRun> {
        const encodedSceneName = encodeURIComponent(sceneName);

        return this.http.post<PipelineRunDto>(`/api/scenes/${encodedSceneName}/pipeline-runs/latest/cancel`, {})
        .pipe(map(mapPipelineRunDtoToPipelineRun));
    }

    getLatestPipelineRun(sceneName: string): Observable<PipelineRun | null> {
        const encodedSceneName = encodeURIComponent(sceneName);

        return this.http.get<PipelineRunDto | null>(`/api/scenes/${encodedSceneName}/pipeline-runs/latest`)
        .pipe(map((pipelineRun) => pipelineRun ? mapPipelineRunDtoToPipelineRun(pipelineRun) : null));
    }

    getLatestPipelineLogs(sceneName: string, stage: string | null = null): Observable<PipelineLog | null> {
        const encodedSceneName = encodeURIComponent(sceneName);
        const query = stage ? `?stage=${encodeURIComponent(stage)}` : '';

        return this.http.get<PipelineLogDto | null>(`/api/scenes/${encodedSceneName}/pipeline-runs/latest/logs${query}`)
        .pipe(map((pipelineLog) => pipelineLog ? mapPipelineLogDtoToPipelineLog(pipelineLog) : null));
    }

}
