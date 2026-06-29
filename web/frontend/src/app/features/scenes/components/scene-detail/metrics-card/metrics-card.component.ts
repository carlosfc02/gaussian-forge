import { Component, Input } from '@angular/core';
import { MetricStage, SceneMetrics } from '../../../../../shared/models/metrics.model';

interface Masked3dgsSummary {
  split: string;
  frameCount: number | null;
  maskedFrameCount: number | null;
  fullImage: Record<string, unknown>;
  maskedObject: Record<string, unknown>;
}

@Component({
  selector: 'app-metrics-card',
  standalone: true,
  templateUrl: './metrics-card.component.html',
  host: { class: 'scene-detail-card scene-detail-card--metrics' },
})
export class MetricsCardComponent {
  @Input() metrics: SceneMetrics | null = null;
  @Input() stages: MetricStage[] = [];

  stageLabel(stage: string): string {
    return (
      {
        bbox_estimate: 'BBox',
        colmap: 'COLMAP',
        train_3dgs: '3DGS training',
        masked_3dgs: '3DGS masked metrics',
        train_sugar: 'SuGaR training',
        masked_sugar: 'SuGaR masked metrics',
      } as Record<string, string>
    )[stage] ?? stage.replace(/_/g, ' ');
  }

  get3dgs(stage: MetricStage): Record<string, unknown> | null {
    const metrics = stage.metrics;
    if (!metrics || Array.isArray(metrics) || !('metrics_3dgs' in metrics)) return null;
    const entries = metrics['metrics_3dgs'];
    const latest = Array.isArray(entries) ? entries.at(-1) : null;
    return this.isRecord(latest) ? latest : null;
  }

  isMaskedObjectStage(stage: string): boolean {
    return stage === 'masked_3dgs' || stage === 'masked_sugar';
  }

  maskedFullTitle(stage: string): string {
    return stage === 'masked_sugar' ? 'SuGaR full image' : '3DGS full image';
  }

  maskedObjectTitle(stage: string): string {
    return stage === 'masked_sugar' ? 'SuGaR masked object' : '3DGS masked object';
  }

  getMasked3dgs(stage: MetricStage): Masked3dgsSummary | null {
    const metrics = stage.metrics;
    if (!this.isRecord(metrics)) return null;
    const splits = metrics['splits'];
    if (!this.isRecord(splits)) return null;
    const preferred = typeof metrics['preferred_split'] === 'string' ? metrics['preferred_split'] : 'test';
    const split = this.isRecord(splits[preferred]) ? preferred : this.isRecord(splits['train']) ? 'train' : Object.keys(splits)[0];
    const summary = splits[split];
    if (!this.isRecord(summary)) return null;
    const fullImage = summary['full_image'];
    const maskedObject = summary['masked_object'];
    if (!this.isRecord(fullImage) || !this.isRecord(maskedObject)) return null;
    return {
      split,
      frameCount: typeof summary['frame_count'] === 'number' ? summary['frame_count'] : null,
      maskedFrameCount: typeof summary['masked_frame_count'] === 'number' ? summary['masked_frame_count'] : null,
      fullImage,
      maskedObject,
    };
  }

  entries(value: Record<string, unknown> | unknown[] | null, limit: number): { key: string; value: string }[] {
    if (!value || Array.isArray(value)) return [];
    return Object.entries(value)
      .filter(([key, item]) => !['splits', 'frames'].includes(key) && item !== null && item !== undefined && !Array.isArray(item))
      .slice(0, limit)
      .map(([key, item]) => ({ key: key.replace(/_/g, ' '), value: this.format(item) }));
  }

  number(record: Record<string, unknown>, key: string): string {
    const value = record[key];
    return typeof value === 'number' ? this.formatNumber(value) : 'n/a';
  }

  duration(seconds: number | null): string {
    if (seconds == null) return 'n/a';
    if (seconds < 60) return `${this.formatNumber(seconds)}s`;
    const minutes = Math.floor(seconds / 60);
    const rest = Math.round(seconds % 60);
    return minutes < 60 ? `${minutes}m ${rest}s` : `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
  }

  private format(value: unknown): string {
    if (typeof value === 'number') return this.formatNumber(value);
    if (typeof value === 'boolean') return value ? 'true' : 'false';
    if (typeof value === 'string') return value;
    if (this.isRecord(value)) return 'exists' in value && 'file_count' in value ? `${value['exists'] ? 'ready' : 'missing'}, ${value['file_count']} files` : JSON.stringify(value);
    return String(value);
  }

  private formatNumber(value: number): string {
    return Number.isInteger(value) ? value.toLocaleString() : value.toLocaleString(undefined, { maximumFractionDigits: 3 });
  }

  private isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
  }
}
