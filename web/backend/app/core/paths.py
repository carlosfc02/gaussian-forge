from pathlib import Path
import os

PROJECT_ROOT = Path(
    os.getenv("GAUSSIANFORGE_ROOT", Path(__file__).resolve().parents[4])
).resolve()

DATA_DIR = PROJECT_ROOT / "data"
VIDEOS_DIR = DATA_DIR / "videos"
FRAMES_VIDEOS_DIR = DATA_DIR / "frames_videos"
MASKS_DIR = DATA_DIR / "masks"
GS_DIR = DATA_DIR / "3dgs"
SUGAR_OUTPUT_DIR = DATA_DIR / "sugar_output"

JOBS_DIR = PROJECT_ROOT / "jobs"   
SEGMENTATION_JOBS_DIR = JOBS_DIR / "segmentation"

LOGS_DIR = PROJECT_ROOT / "logs"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

def ensure_base_directories():
    directories = [
        DATA_DIR,
        VIDEOS_DIR,
        FRAMES_VIDEOS_DIR,
        MASKS_DIR,
        GS_DIR,
        SUGAR_OUTPUT_DIR,
        JOBS_DIR,
        SEGMENTATION_JOBS_DIR,
        LOGS_DIR,
        SCRIPTS_DIR
    ]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
