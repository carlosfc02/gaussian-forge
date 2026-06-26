import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { HealthService } from '../../../core/services/health.service';
import { AppSidebarComponent } from './app-sidebar';

describe('AppSidebarComponent', () => {
  let healthService: { getHealth: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    vi.useFakeTimers();
    healthService = { getHealth: vi.fn() };
    TestBed.configureTestingModule({
      imports: [AppSidebarComponent],
      providers: [provideRouter([]), { provide: HealthService, useValue: healthService }],
    });
  });

  afterEach(() => vi.useRealTimers());

  it('starts checking, reports a failure and recovers on the next poll', async () => {
    healthService.getHealth
      .mockReturnValueOnce(throwError(() => new Error('offline')))
      .mockReturnValueOnce(of({ status: 'ok', projectRoot: '/', videosDir: '/data', scriptsDir: '/scripts' }));

    const fixture = TestBed.createComponent(AppSidebarComponent);
    const component = fixture.componentInstance;

    expect(component.backendStatus()).toBe('checking');

    await vi.advanceTimersByTimeAsync(0);
    fixture.detectChanges();
    expect(component.backendStatus()).toBe('disconnected');
    expect(component.backendStatusLabel()).toBe('Backend disconnected');

    await vi.advanceTimersByTimeAsync(5000);
    fixture.detectChanges();
    expect(component.backendStatus()).toBe('connected');
    expect(component.backendStatusLabel()).toBe('Backend connected');
    expect(healthService.getHealth).toHaveBeenCalledTimes(2);
  });

  it('treats a non-ok health response as disconnected', async () => {
    healthService.getHealth.mockReturnValue(of({ status: 'degraded', projectRoot: '/', videosDir: '/data', scriptsDir: '/scripts' }));

    const fixture = TestBed.createComponent(AppSidebarComponent);
    await vi.advanceTimersByTimeAsync(0);

    expect(fixture.componentInstance.backendStatus()).toBe('disconnected');
  });
});
