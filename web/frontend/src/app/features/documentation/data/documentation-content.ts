import { DocumentationCallout, DocumentationSection, DocumentationStep, PipelineRecipe } from '../../../shared/models/documentation.model';

export const DOCUMENTATION_SECTIONS: DocumentationSection[] = [
  { id: 'overview', title: 'Overview', description: 'How GaussianForge turns a video into 3DGS and SuGaR results.', keywords: ['pipeline', 'workflow', 'reconstruction'], category: 'basic' },
  { id: 'basic-dashboard', title: 'Dashboard and project states', description: 'Monitor scenes, progress, health and generated assets.', keywords: ['dashboard', 'status', 'progress'], category: 'basic' },
  { id: 'basic-create-project', title: 'Create a project', description: 'Upload a supported video and create the scene workspace.', keywords: ['upload', 'video', 'scene'], category: 'basic' },
  { id: 'basic-run-pipeline', title: 'Run the pipeline', description: 'Choose a preset, start processing and cancel safely.', keywords: ['preset', 'fast', 'balanced', 'quality', 'cancel'], category: 'basic' },
  { id: 'basic-monitor-results', title: 'Monitor and inspect results', description: 'Read live logs, metrics, assets and open local viewers.', keywords: ['logs', 'metrics', 'viewer', 'assets'], category: 'basic' },
  { id: 'advanced-execution', title: 'Advanced execution modes', description: 'Run the full pipeline, one stage or a custom ordered selection.', keywords: ['full', 'stage', 'custom', 'run until'], category: 'advanced' },
  { id: 'advanced-stages', title: 'Pipeline stages', description: 'Understand stage order, dependencies and outputs.', keywords: ['bbox', 'sam2', 'colmap', '3dgs', 'sugar'], category: 'advanced' },
  { id: 'advanced-common', title: 'Common options', description: 'Overwrite, evaluation, mask loss and background settings.', keywords: ['force', 'metrics', 'loss', 'background'], category: 'advanced' },
  { id: 'advanced-paths', title: 'Path options', description: 'Control jobs, masks, datasets and model output directories.', keywords: ['path', 'directory', 'job'], category: 'advanced' },
  { id: 'advanced-bbox', title: 'BBox options', description: 'Configure the initial SAM 2 object prompt.', keywords: ['bbox', 'checkpoint', 'runner'], category: 'advanced' },
  { id: 'advanced-frames', title: 'Segmentation and dataset options', description: 'Control temporal sampling and dataset preparation.', keywords: ['frame step', 'sam2', 'dataset'], category: 'advanced' },
  { id: 'advanced-colmap', title: 'COLMAP options', description: 'Configure matching, cameras, GPU and reusable intermediate data.', keywords: ['matcher', 'camera', 'sift', 'mapping'], category: 'advanced' },
  { id: 'advanced-3dgs', title: '3DGS options', description: 'Configure training length, resolution, evaluation and masks.', keywords: ['iterations', 'resolution', 'eval'], category: 'advanced' },
  { id: 'advanced-sugar', title: 'SuGaR options', description: 'Configure refinement, surface extraction, exports and cleanup.', keywords: ['mesh', 'regularization', 'refinement', 'export'], category: 'advanced' },
  { id: 'advanced-recipes', title: 'Practical recipes', description: 'Recommended stage combinations for common workflows.', keywords: ['recipe', 'segmentation only', 'metrics only'], category: 'advanced' },
];

export const BASIC_WORKFLOW_STEPS: DocumentationStep[] = [
  { number: '01', title: 'Create a project', description: 'Open New Project, enter a unique scene name and upload an MP4, MKV, MOV or AVI video.', details: ['Scene names use letters, numbers, underscores and hyphens.', 'The video becomes the stable source for every later stage.'] },
  { number: '02', title: 'Choose a preset', description: 'Open the project detail and select Fast, Balanced or Quality.', details: ['Fast validates the workflow and stops after 3DGS.', 'Balanced is the recommended default.', 'Quality processes every frame and performs the longest training.'] },
  { number: '03', title: 'Select the object', description: 'When bbox selection starts, draw a tight rectangle around the target object in the local selector.', details: ['Include the complete object.', 'Prefer a sharp frame with little occlusion.'] },
  { number: '04', title: 'Monitor processing', description: 'Follow the project status and Stage logs while SAM 2, COLMAP, 3DGS and SuGaR run.', details: ['Logs refresh every two seconds.', 'Cancel stops the active run and its child process tree.'] },
  { number: '05', title: 'Inspect results', description: 'Review metrics and generated assets, then open the local 3DGS or SuGaR viewer.', details: ['Viewer buttons launch Linux/WSL Docker viewer windows on the backend workstation.', 'Generated assets remain under the project data directories.'] },
];

export const BASIC_CALLOUTS: Record<string, DocumentationCallout> = {
  status: { tone: 'info', title: 'Status is inferred from real artifacts', content: 'The project status combines active pipeline manifests with generated masks, datasets, COLMAP output, 3DGS checkpoints and SuGaR artifacts.' },
  cancel: { tone: 'warning', title: 'One active run per scene', content: 'GaussianForge blocks a second pipeline run for the same scene. Cancel or wait for the current run before starting another configuration.' },
  viewers: { tone: 'info', title: 'Viewers are local applications', content: 'The web buttons launch Linux/WSL Docker viewer scripts on the machine running the backend. They are not embedded browser viewers.' },
};

export const PIPELINE_RECIPES: PipelineRecipe[] = [
  { id: 'segmentation-only', title: 'Segmentation only', description: 'Generate or regenerate SAM 2 masks without touching reconstruction output.', mode: 'Single stage', stages: ['segment_video'], notes: ['Requires an existing job when bbox selection is not included.', 'Set Frame step to 1 to process every video frame.'] },
  { id: 'segmentation-dataset', title: 'Segmentation + prepare dataset', description: 'Regenerate masks and immediately rebuild COLMAP/3DGS input folders.', mode: 'Custom stages', stages: ['segment_video', 'prepare_3dgs_dataset'], notes: ['Use the quick selection button with the same name.', 'Existing later-stage models remain untouched.'] },
  { id: 'until-3dgs', title: 'Run until 3DGS', description: 'Execute the complete reconstruction path but stop before SuGaR.', mode: 'Custom stages', stages: ['select_bbox', 'segment_video', 'prepare_3dgs_dataset', 'run_colmap_pipeline', 'train_3dgs'], notes: ['Useful when only Gaussian rendering is required.', 'Fast behaves similarly by default.'] },
  { id: 'sugar-existing', title: 'SuGaR from an existing 3DGS model', description: 'Reuse masks, dataset, COLMAP and the stable gs/model checkpoint.', mode: 'Single stage', stages: ['train_sugar'], notes: ['The 3DGS model should normally contain iteration 7000 or later.', 'Fast can still run SuGaR when this stage is selected explicitly.'] },
  { id: 'metrics-only', title: 'SuGaR metrics only', description: 'Evaluate matching existing 3DGS and refined SuGaR checkpoints.', mode: 'Single stage', stages: ['sugar_metrics'], notes: ['No SuGaR retraining is performed.', 'The refined checkpoint must match the model expected by the official metrics script.'] },
];