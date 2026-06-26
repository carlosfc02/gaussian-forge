import { SceneStatus } from '../models/scene-status.model';
import { getSceneStatusMeta, isSceneHealthy, isSceneTerminal } from './scene-presentation';

describe('scene presentation', () => {
  it('represents SuGaR ready as a healthy completed state', () => {
    expect(getSceneStatusMeta(SceneStatus.SUGAR_READY).progress).toBe(100);
    expect(isSceneTerminal(SceneStatus.SUGAR_READY)).toBe(true);
    expect(isSceneHealthy(SceneStatus.SUGAR_READY)).toBe(true);
  });
});
