import { Component, Input } from '@angular/core';
import { MetricStage, SceneMetrics } from '../../../../../shared/models/metrics.model';
@Component({ selector: 'app-metrics-card', standalone: true, templateUrl: './metrics-card.component.html', host: { class: 'scene-detail-card scene-detail-card--metrics' } })
export class MetricsCardComponent {
 @Input() metrics: SceneMetrics | null = null; @Input() stages: MetricStage[] = [];
 stageLabel(stage: string): string { return ({ bbox_estimate: 'BBox', colmap: 'COLMAP', train_3dgs: '3DGS training', train_sugar: 'SuGaR training' } as Record<string,string>)[stage] ?? stage.replace(/_/g, ' '); }
 get3dgs(stage: MetricStage): Record<string, unknown> | null { const metrics = stage.metrics; if (!metrics || Array.isArray(metrics) || !('metrics_3dgs' in metrics)) return null; const entries = metrics['metrics_3dgs']; const latest = Array.isArray(entries) ? entries.at(-1) : null; return this.isRecord(latest) ? latest : null; }
 entries(value: Record<string, unknown> | unknown[] | null, limit: number): { key: string; value: string }[] { if (!value || Array.isArray(value)) return []; return Object.entries(value).filter(([, item]) => item !== null && item !== undefined && !Array.isArray(item)).slice(0, limit).map(([key,item]) => ({ key: key.replace(/_/g,' '), value: this.format(item) })); }
 number(record: Record<string, unknown>, key: string): string { const value = record[key]; return typeof value === 'number' ? this.formatNumber(value) : 'n/a'; }
 duration(seconds: number | null): string { if (seconds == null) return 'n/a'; if (seconds < 60) return `${this.formatNumber(seconds)}s`; const minutes = Math.floor(seconds/60); const rest = Math.round(seconds%60); return minutes < 60 ? `${minutes}m ${rest}s` : `${Math.floor(minutes/60)}h ${minutes%60}m`; }
 private format(value: unknown): string { if (typeof value === 'number') return this.formatNumber(value); if (typeof value === 'boolean') return value ? 'true' : 'false'; if (typeof value === 'string') return value; if (this.isRecord(value)) return 'exists' in value && 'file_count' in value ? `${value['exists'] ? 'ready' : 'missing'}, ${value['file_count']} files` : JSON.stringify(value); return String(value); }
 private formatNumber(value: number): string { return Number.isInteger(value) ? value.toLocaleString() : value.toLocaleString(undefined, { maximumFractionDigits: 3 }); }
 private isRecord(value: unknown): value is Record<string, unknown> { return typeof value === 'object' && value !== null && !Array.isArray(value); }
}