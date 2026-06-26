# GaussianForge

GaussianForge is a Linux/WSL-first web application and reproducible pipeline for object-centric 3D reconstruction from video. It combines SAM 2 segmentation, COLMAP camera reconstruction, 3D Gaussian Splatting training, SuGaR mesh refinement, metrics, downloads and local viewers.

## What It Does

1. Upload a video and create a scene from the web UI.
2. Select the target object with an interactive bounding box.
3. Segment the object through the video with SAM 2.
4. Prepare a COLMAP/3DGS dataset.
5. Run COLMAP, train 3DGS and optionally train SuGaR.
6. Inspect logs, metrics, generated assets and local Linux/WSL viewers from the web.

## Requirements

GaussianForge is intended to run on Linux or WSL2 with WSLg.

Required software:

- Git
- Python 3.10+
- Node.js 22 LTS and npm
- ffmpeg
- Docker with Docker Compose
- NVIDIA GPU drivers
- NVIDIA Container Toolkit, or Docker Desktop with WSL2 GPU integration
- A graphical Linux session for the viewers, for example WSLg or X11

Check Docker GPU access:

```bash
docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
```

## Quick Start

Clone the repository:

```bash
git clone <REPOSITORY_URL>
cd TFG
```

Build the pipeline containers:

```bash
docker compose build sam2-seg colmap gaussian-splatting sugar viewer
```

Install backend dependencies:

```bash
cd web/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ../..
```

Install frontend dependencies:

```bash
cd web/frontend
npm install
cd ../..
```

Download the SAM 2 checkpoint. The default used by the web is `sam2.1_hiera_small`:

```bash
docker compose run --rm sam2-seg python /app/scripts/bootstrap_checkpoints.py --checkpoint sam2.1_hiera_small
```

Supported checkpoint names:

- `sam2.1_hiera_tiny`
- `sam2.1_hiera_small`
- `sam2.1_hiera_base_plus`
- `sam2.1_hiera_large`

To download the checkpoint you want to use, replace the name:

```bash
docker compose run --rm sam2-seg python /app/scripts/bootstrap_checkpoints.py --checkpoint sam2.1_hiera_large
```

To download all supported checkpoints:

```bash
docker compose run --rm sam2-seg python /app/scripts/bootstrap_checkpoints.py --checkpoint all
```

Start the backend:

```bash
cd web/backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Start the frontend in another terminal:

```bash
cd web/frontend
npm start
```

Open:

```text
http://localhost:4200
```

Backend health check:

```text
http://127.0.0.1:8000/api/health
```

## First Test Scene

1. Open `http://localhost:4200`.
2. Create a new project with an `.mp4`, `.mkv`, `.mov` or `.avi` video.
3. Open the project detail page.
4. Select the `Fast` preset.
5. Click `Run pipeline`.
6. Draw the object bounding box when the selector opens.
7. Follow progress and logs from the project page.

`Fast` is the recommended first test because it runs up to 3DGS and skips SuGaR by default.

## Useful Commands

Build everything:

```bash
docker compose build sam2-seg colmap gaussian-splatting sugar viewer
```

Run backend tests:

```bash
cd web/backend
.venv/bin/python -m unittest discover -s tests -v
```

Compile frontend:

```bash
cd web/frontend
node node_modules/typescript/bin/tsc -p tsconfig.app.json --noEmit
```

Open a trained 3DGS scene manually:

```bash
scripts/open_3dgs_viewer.sh --scene-dir 3dgs/<scene_name>
```

## Documentation

- Detailed usage and script reference: [`docs/USAGE.md`](docs/USAGE.md)
- API docs when the backend is running: `http://127.0.0.1:8000/docs`
- In-app documentation page: `http://localhost:4200/documentation`

## Main Directories

- `web/backend/`: FastAPI backend.
- `web/frontend/`: Angular frontend.
- `scripts/`: host orchestration and utility scripts.
- `docker/`: Docker images for SAM 2, COLMAP, 3DGS, SuGaR and the viewer.
- `data/videos/`: uploaded/input videos.
- `data/masks/`: SAM 2 masks.
- `data/3dgs/`: COLMAP datasets and 3DGS models.
- `data/sugar_output/`: SuGaR outputs.
- `logs/`: pipeline and viewer logs.
- `models/sam2/`: SAM 2 checkpoints.

## Credits

GaussianForge is developed as a Final Degree Project at the ULPGC with the collaboration of tutor Jose Miguel Santana Nunez.
