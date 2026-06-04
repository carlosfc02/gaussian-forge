import { Component, effect, input, signal } from '@angular/core';

@Component({
  selector: 'app-scene-video-thumbnail',
  standalone: true,
  templateUrl: './scene-video-thumbnail.component.html',
  styleUrl: './scene-video-thumbnail.component.scss',
})
export class SceneVideoThumbnailComponent {
  readonly thumbnailUrl = input<string | null>(null);
  readonly sceneName = input('');
  readonly compact = input(false);

  readonly imageReady = signal(false);
  readonly isLoading = signal(false);
  readonly hasError = signal(false);

  constructor() {
    effect(() => {
      const thumbnailUrl = this.thumbnailUrl();

      if (!thumbnailUrl) {
        this.imageReady.set(false);
        this.isLoading.set(false);
        this.hasError.set(true);
        return;
      }

      this.imageReady.set(false);
      this.isLoading.set(true);
      this.hasError.set(false);
    });
  }

  onLoad(): void {
    this.imageReady.set(true);
    this.isLoading.set(false);
    this.hasError.set(false);
  }

  onError(): void {
    this.imageReady.set(false);
    this.isLoading.set(false);
    this.hasError.set(true);
  }
}
