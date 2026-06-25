import { AfterViewInit, Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';
import { PIPELINE_OPTION_GROUPS, PIPELINE_OPTIONS, PIPELINE_PRESETS, PIPELINE_STAGES } from '../../shared/data/pipeline-catalog';
import { DocumentationSection, PipelineOptionDefinition, PipelineOptionGroupDefinition } from '../../shared/models/documentation.model';
import { DocumentationCalloutComponent } from './components/documentation-callout/documentation-callout.component';
import { DocumentationNavComponent } from './components/documentation-nav/documentation-nav.component';
import { DocumentationSearchComponent } from './components/documentation-search/documentation-search.component';
import { DocumentationSectionComponent } from './components/documentation-section/documentation-section.component';
import { DocumentationWorkflowComponent } from './components/documentation-workflow/documentation-workflow.component';
import { PipelineOptionGroupComponent } from './components/pipeline-option-group/pipeline-option-group.component';
import { PipelineStageReferenceComponent } from './components/pipeline-stage-reference/pipeline-stage-reference.component';
import { PresetComparisonComponent } from './components/preset-comparison/preset-comparison.component';
import { BASIC_CALLOUTS, BASIC_WORKFLOW_STEPS, DOCUMENTATION_SECTIONS, PIPELINE_RECIPES } from './data/documentation-content';

interface VisibleOptionGroup { group: PipelineOptionGroupDefinition; options: PipelineOptionDefinition[]; }

@Component({
  selector: 'app-documentation',
  standalone: true,
  imports: [DocumentationCalloutComponent, DocumentationNavComponent, DocumentationSearchComponent, DocumentationSectionComponent, DocumentationWorkflowComponent, PipelineOptionGroupComponent, PipelineStageReferenceComponent, PresetComparisonComponent],
  templateUrl: './documentation.component.html',
  styleUrl: './documentation.component.scss',
})
export class DocumentationComponent implements AfterViewInit {
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);
  private observer: IntersectionObserver | null = null;

  readonly query = signal('');
  readonly activeSection = signal('overview');
  readonly sections = DOCUMENTATION_SECTIONS;
  readonly workflowSteps = BASIC_WORKFLOW_STEPS;
  readonly callouts = BASIC_CALLOUTS;
  readonly presets = Object.values(PIPELINE_PRESETS);
  readonly stages = PIPELINE_STAGES;
  readonly recipes = PIPELINE_RECIPES;

  readonly optionGroups = computed<VisibleOptionGroup[]>(() => {
    const query = this.normalizedQuery();
    return PIPELINE_OPTION_GROUPS.map((group) => ({
      group,
      options: PIPELINE_OPTIONS.filter((option) => option.group === group.id && this.optionMatches(option, query)),
    })).filter(({ group, options }) => !query || options.length > 0 || this.textMatches([group.label, group.description], query));
  });

  readonly visibleSections = computed(() => this.sections.filter((section) => this.sectionMatches(section, this.normalizedQuery())));
  readonly hasResults = computed(() => this.visibleSections().length > 0);

  constructor() {
    this.route.fragment.pipe(takeUntilDestroyed()).subscribe((fragment) => {
      if (fragment && this.sections.some((section) => section.id === fragment)) {
        this.activeSection.set(fragment);
        setTimeout(() => this.scrollToSection(fragment, false));
      }
    });
    this.destroyRef.onDestroy(() => this.observer?.disconnect());
  }

  ngAfterViewInit(): void {
    if (typeof IntersectionObserver === 'undefined') return;
    this.observer = new IntersectionObserver((entries) => {
      const visible = entries.filter((entry) => entry.isIntersecting).sort((left, right) => left.boundingClientRect.top - right.boundingClientRect.top)[0];
      if (visible?.target.id) this.activeSection.set(visible.target.id);
    }, { rootMargin: '-15% 0px -70% 0px', threshold: [0, 0.1] });
    this.observeSections();
  }

  setQuery(value: string): void {
    this.query.set(value);
    setTimeout(() => this.observeSections());
  }

  navigate(sectionId: string): void {
    this.activeSection.set(sectionId);
    void this.router.navigate([], { fragment: sectionId, replaceUrl: true });
    this.scrollToSection(sectionId, true);
  }

  isVisible(sectionId: string): boolean {
    return this.visibleSections().some((section) => section.id === sectionId);
  }

  section(sectionId: string): DocumentationSection {
    return this.sections.find((section) => section.id === sectionId)!;
  }

  optionGroup(sectionId: string): VisibleOptionGroup | undefined {
    return this.optionGroups().find(({ group }) => group.documentationFragment === sectionId);
  }

  private normalizedQuery(): string { return this.query().trim().toLowerCase(); }

  private sectionMatches(section: DocumentationSection, query: string): boolean {
    if (!query) return true;
    if (this.textMatches([section.title, section.description, ...section.keywords], query)) return true;
    const group = PIPELINE_OPTION_GROUPS.find((item) => item.documentationFragment === section.id);
    return !!group && PIPELINE_OPTIONS.some((option) => option.group === group.id && this.optionMatches(option, query));
  }

  private optionMatches(option: PipelineOptionDefinition, query: string): boolean {
    return !query || this.textMatches([String(option.key), option.label, option.description, option.effect, option.recommendation ?? '', option.warning ?? '', ...(option.allowedValues ?? []), ...option.keywords], query);
  }

  private textMatches(values: string[], query: string): boolean { return values.some((value) => value.toLowerCase().includes(query)); }

  private observeSections(): void {
    if (!this.observer) return;
    this.observer.disconnect();
    document.querySelectorAll<HTMLElement>('[data-doc-section]').forEach((section) => this.observer!.observe(section));
  }

  private scrollToSection(sectionId: string, smooth: boolean): void {
    const element = document.getElementById(sectionId);
    if (element && typeof element.scrollIntoView === 'function') {
      element.scrollIntoView({ behavior: smooth ? 'smooth' : 'auto', block: 'start' });
    }
  }
}