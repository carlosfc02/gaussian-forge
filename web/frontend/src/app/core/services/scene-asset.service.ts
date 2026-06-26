import { DOCUMENT } from '@angular/common';
import { HttpClient, HttpResponse } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { map, Observable } from 'rxjs';

export type SceneAssetKind = '3dgs-ply' | 'sugar-ply' | 'sugar-obj';

const FALLBACK_FILENAMES: Record<SceneAssetKind, (sceneName: string) => string> = {
  '3dgs-ply': (sceneName) => `${sceneName}_3dgs.ply`,
  'sugar-ply': (sceneName) => `${sceneName}_sugar.ply`,
  'sugar-obj': (sceneName) => `${sceneName}_sugar_obj.zip`,
};

@Injectable({ providedIn: 'root' })
export class SceneAssetService {
  private readonly http = inject(HttpClient);
  private readonly document = inject(DOCUMENT);

  download(sceneName: string, asset: SceneAssetKind): Observable<string> {
    const encodedSceneName = encodeURIComponent(sceneName);
    return this.http
      .get(`/api/scenes/${encodedSceneName}/assets/${asset}`, {
        observe: 'response',
        responseType: 'blob',
      })
      .pipe(
        map((response) => {
          const filename = this.getFilename(response, FALLBACK_FILENAMES[asset](sceneName));
          this.saveBlob(response.body, filename);
          return filename;
        }),
      );
  }

  private getFilename(response: HttpResponse<Blob>, fallback: string): string {
    const disposition = response.headers.get('content-disposition');
    if (!disposition) return fallback;

    const encodedMatch = disposition.match(/filename\*=UTF-8''([^;]+)/i);
    if (encodedMatch?.[1]) return decodeURIComponent(encodedMatch[1].replace(/["']/g, ''));

    const filenameMatch = disposition.match(/filename="?([^";]+)"?/i);
    return filenameMatch?.[1] ?? fallback;
  }

  private saveBlob(blob: Blob | null, filename: string): void {
    if (!blob) return;

    const url = URL.createObjectURL(blob);
    const anchor = this.document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    anchor.style.display = 'none';
    this.document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }
}
