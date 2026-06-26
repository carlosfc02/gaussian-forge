import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { SceneStatus } from '../../shared/models/scene-status.model';
import { SceneService } from './scene.service';

const sceneDto = {
  name: 'my scene',
  status: SceneStatus.VIDEO_UPLOADED,
  video_path: 'videos/a.mp4',
  masks_path: '',
  gs_path: '',
  sugar_output_path: '',
  gs_ply_available: true,
  sugar_ply_available: false,
  sugar_obj_available: false,
  pipeline_run: null,
};

describe('SceneService', () => {
  let service: SceneService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(SceneService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('loads and maps a scene', () => {
    let value: any;
    service.getSceneByName('my scene').subscribe((scene) => value = scene);
    http.expectOne('/api/scenes/my%20scene').flush(sceneDto);
    expect(value.videoUrl).toBe('/api/scenes/my%20scene/video');
    expect(value.gsPlyAvailable).toBe(true);
    expect(value.pipelineRun).toBeNull();
  });

  it('clears generated data and maps the updated scene', () => {
    let value: any;
    service.clearGeneratedData('my scene').subscribe((scene) => value = scene);
    const request = http.expectOne('/api/scenes/my%20scene/data');
    expect(request.request.method).toBe('DELETE');
    request.flush({ ...sceneDto, gs_ply_available: false });
    expect(value.gsPlyAvailable).toBe(false);
  });
});
