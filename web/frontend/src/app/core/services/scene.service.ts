import { HttpClient } from "@angular/common/http";
import { inject, Injectable } from "@angular/core";
import { map, Observable } from 'rxjs'

import { Scene } from "../../shared/models/scene.model";
import { SceneDto } from "../../shared/dtos/scene.dto";
import { mapSceneDtosToScene, mapSceneDtoToScene } from "../mappers/scene.mapper";


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
        return this.http.get<SceneDto>(`/api/scenes/${sceneName}`)
        .pipe(map(mapSceneDtoToScene));
    }

}