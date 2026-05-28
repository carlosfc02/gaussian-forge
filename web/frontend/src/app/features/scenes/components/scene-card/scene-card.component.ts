import { Component, Input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { Scene } from '../../../../shared/models/scene.model';

@Component({
    selector: 'app-scene-card',
    standalone: true,
    imports: [RouterLink],
    templateUrl: './scene-card.component.html',
    styleUrl: './scene-card.component.scss'
})
export class SceneCardComponent {
    @Input({ required: true }) scene!: Scene;

}