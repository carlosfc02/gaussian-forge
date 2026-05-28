import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { NgbTooltip } from '@ng-bootstrap/ng-bootstrap';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, NgbTooltip],
  templateUrl: './app-sidebar.html',
  styleUrls: ['./app-sidebar.scss'],
})
export class AppSidebarComponent {
}
