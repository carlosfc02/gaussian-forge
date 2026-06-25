import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { DocumentationComponent } from './documentation.component';

describe('DocumentationComponent', () => {
  let fixture: ComponentFixture<DocumentationComponent>;
  let component: DocumentationComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [DocumentationComponent], providers: [provideRouter([])] }).compileComponents();
    fixture = TestBed.createComponent(DocumentationComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('shows basic and advanced sections by default', () => {
    expect(component.visibleSections().some((section) => section.id === 'basic-run-pipeline')).toBe(true);
    expect(component.visibleSections().some((section) => section.id === 'advanced-sugar')).toBe(true);
  });

  it('filters sections and options instantly', () => {
    component.setQuery('frame step');
    expect(component.visibleSections().map((section) => section.id)).toContain('advanced-frames');
    expect(component.optionGroup('advanced-frames')?.options.map((option) => option.key)).toContain('frameStep');
    expect(component.visibleSections().map((section) => section.id)).not.toContain('advanced-sugar');
  });

  it('shows an empty state for an unknown query', () => {
    component.setQuery('not-a-real-gaussianforge-option');
    expect(component.hasResults()).toBe(false);
  });

  it('updates the URL fragment when navigating', async () => {
    const router = TestBed.inject(Router);
    component.navigate('advanced-colmap');
    await fixture.whenStable();
    expect(router.url).toContain('#advanced-colmap');
  });
});