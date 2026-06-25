import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: 'dashboard',
    loadComponent: () =>
      import('./features/dashboard/dashboard.component').then(
        (module) => module.DashboardComponent,
      ),
  },
  {
    path: 'new-project',
    loadComponent: () =>
      import('./features/new-project/new-project.component').then(
        (module) => module.NewProjectComponent,
      ),
  },
  {
    path: 'documentation',
    loadComponent: () =>
      import('./features/documentation/documentation.component').then(
        (module) => module.DocumentationComponent,
      ),
  },
  {
    path: 'scenes/:sceneName',
    loadComponent: () =>
      import('./features/scenes/scene-detail.component').then(
        (module) => module.SceneDetailComponent,
      ),
  },
  {
    path: '',
    redirectTo: 'dashboard',
    pathMatch: 'full',
  },
  {
    path: '**',
    redirectTo: 'dashboard',
  },
];
