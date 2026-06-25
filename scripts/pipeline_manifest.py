from __future__ import annotations

import json
import os
import shlex
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_command_string(command: list[str]) -> str:
    return shlex.join(command)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.replace(path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def archive_stage_manifest(scene_dir: Path, stage: str, payload: dict) -> Path:
    metrics_dir = scene_dir / "metrics" / stage
    metrics_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    manifest_path = metrics_dir / f"{timestamp}.json"
    write_json(manifest_path, payload)
    return manifest_path
