import { Component, Input } from '@angular/core';
import { Scene } from '../../../../shared/models/scene.model';
import { SceneCardComponent } from '../scene-card/scene-card.component';

@Component({
  selector: 'app-scenes-list',
  imports: [SceneCardComponent],
  templateUrl: './scenes-list.component.html',
  styleUrl: './scenes-list.component.scss',
})
export class ScenesListComponent {
  @Input({ required: true }) scenes: Scene[] = [];

}
