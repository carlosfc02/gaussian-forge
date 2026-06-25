import { Component, EventEmitter, Input, Output } from '@angular/core';
@Component({ selector: 'app-documentation-search', standalone: true, templateUrl: './documentation-search.component.html', styleUrl: './documentation-search.component.scss' })
export class DocumentationSearchComponent { @Input() query = ''; @Output() queryChange = new EventEmitter<string>(); }