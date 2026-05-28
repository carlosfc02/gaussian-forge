import { AsyncPipe } from "@angular/common";
import { Component, inject } from "@angular/core";
import { RouterLink } from "@angular/router";
import { SceneService } from "../../core/services/scene.service";
import { ScenesListComponent } from "../scenes/components/scenes-list/scenes-list.component";
import { tap } from "rxjs";

@Component({
    selector: 'app-dashboard',
    standalone: true,
    imports: [AsyncPipe, RouterLink, ScenesListComponent],
    templateUrl: './dashboard.component.html',
    styleUrl: './dashboard.component.scss'
})
export class DashboardComponent  {
    private readonly sceneService = inject(SceneService);

    readonly scenes$ = this.sceneService.getScenes();

}