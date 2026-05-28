import { SceneStatus } from '../models/scene-status.model';

export interface Scene {
    name: string;
    status: SceneStatus;
    videoPath: string | null ;
    maskPaths: string | null;
    gsPath: string | null;
    sugarOutputPath: string | null;
}