from fastapi import APIRouter

from app.core.paths import PROJECT_ROOT, VIDEOS_DIR, SCRIPTS_DIR

router = APIRouter(prefix="/health", tags=["health"])

@router.get("")
def health_check():
    return {
        "status": "ok",
        "project_root": str(PROJECT_ROOT),
        "videos_dir": str(VIDEOS_DIR),
        "scripts_dir": str(SCRIPTS_DIR),
    }