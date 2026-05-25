# GaussianForge

GaussianForge is a reproducible pipeline for object-centric 3D reconstruction from video using SAM 2, COLMAP, 3D Gaussian Splatting, and SuGaR.

## Current components

- `sam2-seg`: GPU-oriented container that segments one object in one video using an initial bounding box on frame `0`.
- `colmap`: CUDA-enabled container for sparse reconstruction from the prepared dataset.
- `gaussian-splatting`: Container for official 3DGS training on the COLMAP output.
- `sugar`: Container for official SuGaR mesh-oriented training on top of the prepared COLMAP dataset and, by default, the vanilla 3DGS checkpoint.
- `tools/3dgs-viewer`: Local Windows viewer binaries for real-time inspection of trained 3DGS scenes.

## Directory layout

- `docker/sam2/`: Docker image definition for SAM 2.
- `docker/colmap/`: Docker image definition for COLMAP.
- `docker/gaussian-splatting/`: Docker image definition for official 3DGS training.
- `docker/sugar/`: Docker image definition for official SuGaR training.
- `scripts/`: host-side orchestration and preprocessing scripts.
- `jobs/segmentation/`: JSON job definitions.
- `data/videos/`: input videos.
- `data/masks/`: output binary masks.
- `data/3dgs/`: prepared datasets and reconstruction outputs for `COLMAP -> 3DGS`.
- `models/sam2/`: external checkpoints volume.
- `logs/`: runtime logs or future artifacts.

## Build

```bash
docker compose build sam2-seg colmap gaussian-splatting sugar
```

## Download a checkpoint

```bash
docker compose run --rm sam2-seg python /app/scripts/bootstrap_checkpoints.py --checkpoint sam2.1_hiera_small
```

Use `--checkpoint all` to fetch every supported SAM 2.1 checkpoint.

## Select a bbox from a video

Run this on the host to open a frame and drag the bounding box with the mouse:

```bash
python scripts/select_bbox.py --video videos/example.mp4 --frame-index 0 --save-preview masks/example_bbox_preview.png
```

The script now also creates a segmentation job automatically by default at:

- `jobs/segmentation/<video_stem>_job.json`

For example, selecting a bbox for `videos/wood_star.mp4` writes:

- `jobs/segmentation/wood_star_job.json`

The generated job uses:

- `output_dir = masks/<video_stem>`
- `object_id = 1`
- `checkpoint = sam2.1_hiera_small`

Useful options:

```bash
python scripts/select_bbox.py --video videos/example.mp4 --job jobs/segmentation/my_scene.json --mask-output-dir masks/my_scene --object-id 1
```

The script still prints a ready-to-paste JSON snippet like:

```json
{"bbox_xyxy": [120, 80, 360, 320]}
```

`--video` and `--save-preview` are resolved relative to `data/`.
`--job` is resolved relative to the repository root.

## Run segmentation

1. Put your video under `data/videos/`.
2. Run `scripts/select_bbox.py` to choose the box and generate the job automatically.
3. Run:

```bash
docker compose run --rm sam2-seg python /app/scripts/segment_video.py --job /jobs/segmentation/example_job.json
```

The output masks and `manifest.json` will be written under `data/masks/...`.

## Prepare a COLMAP / 3DGS dataset from SAM 2 masks

This step runs on the host and builds a dataset that keeps only the segmented object:

```bash
python scripts/prepare_3dgs_dataset.py --job jobs/segmentation/wood_star_job.json
```

By default it creates:

- `data/3dgs/<scene>/colmap/images`: original RGB frames aligned with the masks
- `data/3dgs/<scene>/colmap/masks`: binary masks for optional COLMAP experiments, saved as `<image_name>.png`
- `data/3dgs/<scene>/gs/images`: masked RGB frames with black background for 3DGS
- `data/3dgs/<scene>/dataset_manifest.json`: metadata and frame indices used

Useful options:

```bash
python scripts/prepare_3dgs_dataset.py --job jobs/segmentation/wood_star_job.json --frame-step 2 --background black
```

Use `--frame-step` if you want to subsample the sequence before COLMAP or 3DGS.

## Run COLMAP before masking the training images

This step now follows the recommended split:

- `COLMAP` estimates cameras from the original RGB frames in `colmap/images`
- `3DGS` later receives the masked images from `gs/images`

That way `COLMAP` can use the full scene context for features and matching, while `3DGS` still learns only the segmented object.

Default command:

```bash
python scripts/run_colmap_pipeline.py --scene-dir 3dgs/wood_star --single-camera --matcher sequential
```

Default behavior:

- CUDA SIFT is enabled by default in `COLMAP`
- SAM 2 masks are not used in `COLMAP` by default
- the script automatically picks the best sparse COLMAP model by registered image count
- the final `gs/source` is created from the masked images with the selected sparse model

Outputs:

- `data/3dgs/<scene>/colmap/database.db`
- `data/3dgs/<scene>/colmap/sparse/<best-model>`
- `data/3dgs/<scene>/gs/source/images`
- `data/3dgs/<scene>/gs/source/sparse/0`

Useful options:

```bash
python scripts/run_colmap_pipeline.py --scene-dir 3dgs/wood_star --single-camera --matcher sequential --sequential-overlap 40
python scripts/run_colmap_pipeline.py --scene-dir 3dgs/wood_star --single-camera --matcher exhaustive
python scripts/run_colmap_pipeline.py --scene-dir 3dgs/wood_star --use-colmap-masks
python scripts/run_colmap_pipeline.py --scene-dir 3dgs/wood_star --no-use-gpu
```

For video captures, `--matcher sequential` and `--single-camera` are usually the right defaults.
If the object is hard to register, try more overlap first, then `exhaustive` matching.

## Train 3D Gaussian Splatting

Once `gs/source` exists, launch 3DGS training with:

```bash
python scripts/train_3dgs.py --scene-dir 3dgs/wood_star --iterations 30000
```

The trained model is written by default to:

- `data/3dgs/<scene>/gs/model`

For a quick smoke test:

```bash
python scripts/train_3dgs.py --scene-dir 3dgs/wood_star --iterations 100
```

## Estimate an automatic SuGaR foreground bbox

Before running SuGaR, you can estimate a 3D foreground box automatically from:

- the selected COLMAP sparse model,
- the aligned SAM 2 masks in `colmap/masks`.

The estimator keeps sparse 3D points whose tracked 2D observations fall inside the object masks often enough, trims sparse outliers with percentiles, and adds a configurable margin.

Default command:

```bash
python scripts/estimate_sugar_bbox.py --scene-dir 3dgs/wood_star
```

Useful options:

```bash
python scripts/estimate_sugar_bbox.py --scene-dir 3dgs/wood_star --min-foreground-ratio 0.7 --erode-pixels 2
python scripts/estimate_sugar_bbox.py --scene-dir 3dgs/wood_star --lower-percentile 2 --upper-percentile 98 --padding-scale 0.03
```

Outputs:

- `data/3dgs/<scene>/sugar_bbox_estimate.json`
- a ready-to-copy `--bboxmin ... --bboxmax ...` command snippet for `train_sugar.py`

## Run SuGaR on top of the prepared COLMAP dataset

The SuGaR launcher consumes the same `gs/source` dataset and, by default, reuses the vanilla `3DGS` checkpoint at `gs/model`.

Default command:

```bash
python scripts/train_sugar.py --scene-dir 3dgs/wood_star
```

Default behavior:

- uses the official `train_full_pipeline.py` from SuGaR
- reuses `data/3dgs/<scene>/gs/model` if it contains `iteration_7000`
- writes official SuGaR `output/` folders under `data/sugar-output/`
- uses `dn_consistency` regularization by default

Main outputs:

- `data/sugar-output/coarse/<scene>`
- `data/sugar-output/coarse_mesh/<scene>`
- `data/sugar-output/refined/<scene>`
- `data/sugar-output/refined_mesh/<scene>`
- `data/sugar-output/refined_ply/<scene>`

Useful options:

```bash
python scripts/train_sugar.py --scene-dir 3dgs/wood_star --high-poly --refinement-time short
python scripts/train_sugar.py --scene-dir 3dgs/wood_star --regularization density
python scripts/train_sugar.py --scene-dir 3dgs/wood_star --from-scratch
python scripts/train_sugar.py --scene-dir 3dgs/wood_star --bboxmin "(0.0,0.0,0.0)" --bboxmax "(1.0,1.0,1.0)"
```

Notes:

- By default the launcher does not use SuGaR's eval split.
- If you reuse an existing vanilla 3DGS model, SuGaR expects `point_cloud/iteration_7000/point_cloud.ply`.
- `--from-scratch` tells SuGaR to train its own initial vanilla 3DGS stage for 7000 iterations.

## Install the local 3DGS viewer on Windows

This downloads the official prebuilt SIBR viewer binaries recommended by the 3DGS authors:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_3dgs_viewer.ps1
```

The viewer binaries are extracted under `tools/3dgs-viewer/viewer-dist`.

Important:

- The official Windows viewer requires `cudart64_12.dll`.
- That means you need a CUDA 12.x runtime/toolkit installed on Windows.
- Having only CUDA 13.x in `PATH` is not enough for this viewer build.

## Open a trained scene in the local 3DGS viewer

To open the real-time viewer for a trained scene:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\open_3dgs_viewer.ps1 -SceneDir 3dgs\wood_star
```

Useful options:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\open_3dgs_viewer.ps1 -SceneDir 3dgs\wood_star -Iteration 100 -LoadImages
```

Notes:

- `-SceneDir` is relative to `data/`.
- If you prefer explicit paths, you can use `-ModelDir` and `-SourceDir` instead.
- If the viewer has interop issues on your machine, retry with `-NoInterop`.
- The real-time viewer executable is `tools/3dgs-viewer/viewer-dist/bin/SIBR_gaussianViewer_app.exe`.
- The launcher now checks for CUDA 12 runtime and stops with a clear message if it is missing.

## Open a SuGaR refined PLY in the local viewer

Use the SuGaR-specific wrapper launcher when you want to inspect a refined `.ply` through the same SIBR viewer:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\open_sugar_viewer.ps1 -PlyPath sugar-output\refined_ply\source\your_model.ply -SourceDir 3dgs\wood_star\gs\source
```

Useful options:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\open_sugar_viewer.ps1 -PlyPath sugar-output\refined_ply\source\your_model.ply -SourceDir 3dgs\wood_star\gs\source -LoadImages
```

Notes:

- `-PlyPath` is resolved relative to `data/` unless you pass an absolute path.
- `-SourceDir` should point to the matching `gs/source` dataset.
- The script creates a temporary viewer-compatible wrapper under `data/sugar-output/viewer/`.

## Job contract

```json
{
  "video_path": "videos/mi_video.mp4",
  "output_dir": "masks/mi_video",
  "object_id": 1,
  "bbox_xyxy": [x1, y1, x2, y2],
  "checkpoint": "sam2.1_hiera_small"
}
```

`video_path` and `output_dir` must be relative to `data/`.

## Credits

GaussianForge is developed as a Final Degree Project at the ULPGC with the collaboration of tutor José Miguel Santana Núñez.
