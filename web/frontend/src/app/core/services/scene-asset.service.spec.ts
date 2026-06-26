import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { SceneAssetService } from './scene-asset.service';

describe('SceneAssetService', () => {
  let service: SceneAssetService;
  let http: HttpTestingController;
  let clickSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:test') });
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() });
    clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(SceneAssetService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    clickSpy.mockRestore();
    http.verify();
  });

  it('downloads a model using the backend filename', () => {
    let filename: string | undefined;
    service.download('my scene', '3dgs-ply').subscribe((value) => filename = value);
    const request = http.expectOne('/api/scenes/my%20scene/assets/3dgs-ply');
    expect(request.request.method).toBe('GET');
    request.flush(new Blob(['ply']), {
      headers: { 'Content-Disposition': 'attachment; filename="my_scene_3dgs_iteration_30000.ply"' },
    });
    expect(filename).toBe('my_scene_3dgs_iteration_30000.ply');
    expect(clickSpy).toHaveBeenCalledOnce();
  });
});
