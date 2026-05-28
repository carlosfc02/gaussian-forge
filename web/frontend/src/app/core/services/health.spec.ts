import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { HealthService } from './health.service';

describe('HealthService', () => {
  let service: HealthService;
  let httpTestingController: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });

    service = TestBed.inject(HealthService);
    httpTestingController = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTestingController.verify();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should map the backend health response to the app model', () => {
    let healthValue:
      | {
          status: string;
          projectRoot: string;
          videosDir: string;
          scriptsDir: string;
        }
      | undefined;

    service.getHealth().subscribe((value) => {
      healthValue = value;
    });

    const request = httpTestingController.expectOne('/api/health');
    expect(request.request.method).toBe('GET');

    request.flush({
      status: 'ok',
      project_root: '/workspace',
      videos_dir: '/workspace/data/videos',
      scripts_dir: '/workspace/scripts',
    });

    expect(healthValue).toEqual({
      status: 'ok',
      projectRoot: '/workspace',
      videosDir: '/workspace/data/videos',
      scriptsDir: '/workspace/scripts',
    });
  });
});
