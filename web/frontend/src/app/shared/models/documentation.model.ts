import { PipelineAdvancedOptions, PipelinePresetName, PipelineStageName } from './pipeline.model';

export type DocumentationCalloutTone = 'info' | 'warning' | 'success';
export type PipelineOptionGroup = 'common' | 'paths' | 'bbox' | 'frames' | 'colmap' | 'gs' | 'sugar';
export type PipelineOptionControl = 'boolean' | 'number' | 'text' | 'select';

export interface DocumentationCallout {
  tone: DocumentationCalloutTone;
  title: string;
  content: string;
}

export interface DocumentationStep {
  number: string;
  title: string;
  description: string;
  details?: string[];
}

export interface DocumentationSection {
  id: string;
  title: string;
  description: string;
  keywords: string[];
  category: 'basic' | 'advanced';
}

export interface PipelineStageDefinition {
  name: PipelineStageName;
  label: string;
  shortLabel: string;
  description: string;
  requires: string;
  produces: string;
  documentationFragment: string;
  keywords: string[];
}

export interface PipelinePresetDefinition {
  name: PipelinePresetName;
  label: string;
  description: string;
  frameStep: number;
  sequentialOverlap: number;
  iterations: number;
  sugarMode: string;
  sugarRefinementTime: 'short' | 'medium' | 'long';
  runSugar: boolean;
  recommendedFor: string;
}

export interface PipelineOptionDefinition {
  key: keyof PipelineAdvancedOptions;
  label: string;
  group: PipelineOptionGroup;
  control: PipelineOptionControl;
  description: string;
  effect: string;
  defaultValue: PipelineAdvancedOptions[keyof PipelineAdvancedOptions] | 'preset-dependent';
  allowedValues?: string[];
  minimum?: number;
  step?: number;
  recommendation?: string;
  warning?: string;
  documentationFragment: string;
  keywords: string[];
}

export interface PipelineOptionGroupDefinition {
  id: PipelineOptionGroup;
  label: string;
  description: string;
  documentationFragment: string;
}

export interface PipelineRecipe {
  id: string;
  title: string;
  description: string;
  mode: string;
  stages: PipelineStageName[];
  notes: string[];
}