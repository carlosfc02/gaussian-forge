import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { AppSidebarComponent } from "./shared/components/app-sidebar/app-sidebar";

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, AppSidebarComponent],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {}
