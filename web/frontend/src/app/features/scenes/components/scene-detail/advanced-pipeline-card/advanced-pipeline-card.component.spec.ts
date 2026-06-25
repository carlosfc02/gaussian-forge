import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { AdvancedPipelineCardComponent } from './advanced-pipeline-card.component';

describe('AdvancedPipelineCardComponent', () => {
  it('links every option group to its documentation fragment', async () => {
    await TestBed.configureTestingModule({ imports: [AdvancedPipelineCardComponent], providers: [provideRouter([])] }).compileComponents();
    const fixture = TestBed.createComponent(AdvancedPipelineCardComponent);
    fixture.componentRef.setInput('selectedPreset', 'balanced');
    fixture.componentRef.setInput('presets', []);
    fixture.detectChanges();
    const links = Array.from(fixture.nativeElement.querySelectorAll('a[href*="documentation"]')) as HTMLAnchorElement[];
    expect(links.map((link) => link.getAttribute('href'))).toEqual(expect.arrayContaining([
      '/documentation#advanced-common', '/documentation#advanced-paths', '/documentation#advanced-bbox', '/documentation#advanced-frames', '/documentation#advanced-colmap', '/documentation#advanced-3dgs', '/documentation#advanced-sugar',
    ]));
  });
});