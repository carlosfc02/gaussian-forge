from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CheckpointSpec:
    name: str
    filename: str
    url: str
    config_relpath: str


CHECKPOINT_SPECS: dict[str, CheckpointSpec] = {
    "sam2.1_hiera_tiny": CheckpointSpec(
        name="sam2.1_hiera_tiny",
        filename="sam2.1_hiera_tiny.pt",
        url="https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_tiny.pt",
        config_relpath="configs/sam2.1/sam2.1_hiera_t.yaml",
    ),
    "sam2.1_hiera_small": CheckpointSpec(
        name="sam2.1_hiera_small",
        filename="sam2.1_hiera_small.pt",
        url="https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_small.pt",
        config_relpath="configs/sam2.1/sam2.1_hiera_s.yaml",
    ),
    "sam2.1_hiera_base_plus": CheckpointSpec(
        name="sam2.1_hiera_base_plus",
        filename="sam2.1_hiera_base_plus.pt",
        url="https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_base_plus.pt",
        config_relpath="configs/sam2.1/sam2.1_hiera_b+.yaml",
    ),
    "sam2.1_hiera_large": CheckpointSpec(
        name="sam2.1_hiera_large",
        filename="sam2.1_hiera_large.pt",
        url="https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_large.pt",
        config_relpath="configs/sam2.1/sam2.1_hiera_l.yaml",
    ),
}

DEFAULT_CHECKPOINT = "sam2.1_hiera_small"


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def get_repo_root() -> Path:
    return Path(os.environ.get("SAM2_REPO_DIR", "/opt/sam2")).resolve()


def get_checkpoint_root() -> Path:
    return Path(os.environ.get("SAM2_CHECKPOINT_DIR", "/models/sam2")).resolve()


def get_data_root() -> Path:
    return Path(os.environ.get("DATA_ROOT", get_project_root() / "data")).resolve()


def resolve_checkpoint_spec(name: str) -> CheckpointSpec:
    try:
        return CHECKPOINT_SPECS[name]
    except KeyError as exc:
        supported = ", ".join(sorted(CHECKPOINT_SPECS))
        raise ValueError(f"Unsupported checkpoint '{name}'. Supported values: {supported}.") from exc


def get_checkpoint_path(name: str) -> Path:
    spec = resolve_checkpoint_spec(name)
    return get_checkpoint_root() / spec.filename


def get_model_config_name(name: str) -> str:
    spec = resolve_checkpoint_spec(name)
    return spec.config_relpath


def get_model_config_path(name: str) -> Path:
    spec = resolve_checkpoint_spec(name)
    return get_repo_root() / "sam2" / spec.config_relpath


def resolve_path_under_root(root: Path, relative_path: str, label: str) -> Path:
    candidate = Path(relative_path)
    if candidate.is_absolute():
        raise ValueError(f"{label} must be relative to {root}. Received absolute path: {relative_path}")

    resolved_root = root.resolve()
    candidate_parts = candidate.parts
    root_name = resolved_root.name

    if candidate_parts and candidate_parts[0] == ".":
        candidate = Path(*candidate_parts[1:])
        candidate_parts = candidate.parts

    if candidate_parts and candidate_parts[0] == root_name:
        candidate = Path(*candidate_parts[1:])

    resolved_candidate = (resolved_root / candidate).resolve()
    if resolved_candidate != resolved_root and resolved_root not in resolved_candidate.parents:
        raise ValueError(f"{label} must stay inside {root}. Received: {relative_path}")
    return resolved_candidate
