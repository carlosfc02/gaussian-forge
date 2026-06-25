import { Component, Input } from '@angular/core';
import { DocumentationSection } from '../../../../shared/models/documentation.model';
@Component({ selector: 'app-documentation-section', standalone: true, templateUrl: './documentation-section.component.html', styleUrl: './documentation-section.component.scss' })
export class DocumentationSectionComponent { @Input({ required: true }) section!: DocumentationSection; }