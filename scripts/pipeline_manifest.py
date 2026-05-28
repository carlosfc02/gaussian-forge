from __future__ import annotations

import json
import shlex
from datetime import datetime, timezone
from pathlib import Path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_command_string(command: list[str]) -> str:
    return shlex.join(command)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def archive_stage_manifest(scene_dir: Path, stage: str, payload: dict) -> Path:
    metrics_dir = scene_dir / "metrics" / stage
    metrics_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    manifest_path = metrics_dir / f"{timestamp}.json"
    write_json(manifest_path, payload)
    return manifest_path
