from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, scenes
from app.core.paths import ensure_base_directories

@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_base_directories()
    yield


app = FastAPI(
    title="GaussianForge API",
    description="Backend API for GaussianForge reconstruction pipeline",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",
        "http://127.0.0.1:4200"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(scenes.router, prefix="/api")

@app.get("/")
def root():
    return {
        "name": "GaussianForge API",
        "status": "running",
        "docs": "/docs",
    }