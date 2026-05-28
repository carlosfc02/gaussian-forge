from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
import time
from pathlib import Path

from pipeline_manifest import archive_stage_manifest, build_command_string, utc_now_iso
from sam2_common import get_data_root, resolve_path_under_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Launch official 3D Gaussian Splatting training on a prepared COLMAP dataset.",
    )
    parser.add_argument(
        "--scene-dir",
        required=True,
        help="Scene directory relative to data/, for example 3dgs/wood_star.",
    )
    parser.add_argument(
        "--model-dir",
        help="Model output directory relative to data/. Defaults to <scene-dir>/gs/model.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=30000,
        help="Training iterations. Defaults to 30000.",
    )
    parser.add_argument(
        "--resolution",
        type=int,
        default=1,
        help="3DGS image resolution argument. Defaults to 1.",
    )
    parser.add_argument(
        "--eval",
        action="store_true",
        help="Enable 3DGS eval split.",
    )
    parser.add_argument(
        "--white-background",
        action="store_true",
        help="Train with white background instead of black.",
    )
    parser.add_argument(
        "--extra-arg",
        action="append",
        default=[],
        help="Extra argument passed through to train.py. Repeatable.",
    )
    return parser.parse_args()


def run_command(command: list[str]) -> None:
    print("[cmd]", shlex.join(command))
    subprocess.run(command, check=True)


def find_latest_iteration_point_cloud(model_dir: Path) -> tuple[int | None, Path | None]:
    point_cloud_root = model_dir / "point_cloud"
    if not point_cloud_root.exists():
        return None, None

    candidates: list[tuple[int, Path]] = []
    for path in point_cloud_root.iterdir():
        if not path.is_dir() or not path.name.startswith("iteration_"):
            continue
        try:
            iteration = int(path.name.split("_", 1)[1])
        except ValueError:
            continue
        point_cloud_path = path / "point_cloud.ply"
        if point_cloud_path.exists():
            candidates.append((iteration, point_cloud_path))

    if not candidates:
        return None, None

    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0]


def main() -> int:
    started = time.time()
    started_at = utc_now_iso()
    args = parse_args()
    data_root = get_data_root()
    scene_dir = resolve_path_under_root(data_root, args.scene_dir, "scene-dir")
    source_dir = scene_dir / "gs" / "source"
    model_dir = resolve_path_under_root(
        data_root,
        args.model_dir or f"{Path(args.scene_dir).as_posix()}/gs/model",
        "model-dir",
    )

    if not source_dir.exists():
        raise FileNotFoundError(f"3DGS source dataset does not exist: {source_dir}")
    if not (source_dir / "images").exists():
        raise FileNotFoundError(f"3DGS source images directory does not exist: {source_dir / 'images'}")
    if not (source_dir / "sparse").exists():
        raise FileNotFoundError(f"3DGS sparse directory does not exist: {source_dir / 'sparse'}")

    source_dir_in_container = f"/data/{source_dir.relative_to(data_root).as_posix()}"
    model_dir_in_container = f"/data/{model_dir.relative_to(data_root).as_posix()}"

    model_dir.mkdir(parents=True, exist_ok=True)

    command = [
        "docker",
        "compose",
        "run",
        "--rm",
        "gaussian-splatting",
        "python",
        "train.py",
        "-s",
        source_dir_in_container,
        "-m",
        model_dir_in_container,
        "--iterations",
        str(args.iterations),
        "-r",
        str(args.resolution),
    ]
    if args.eval:
        command.append("--eval")
    if args.white_background:
        command.append("--white_background")
    command.extend(args.extra_arg)

    run_command(command)
    final_iteration, final_point_cloud = find_latest_iteration_point_cloud(model_dir)
    finished_at = utc_now_iso()
    duration_seconds = time.time() - started
    manifest = {
        "status": "success",
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": round(duration_seconds, 3),
        "command": build_command_string(command),
        "scene_dir": str(scene_dir),
        "input_paths": {
            "source_dir": str(source_dir),
        },
        "output_paths": {
            "model_dir": str(model_dir),
            "final_point_cloud": str(final_point_cloud) if final_point_cloud else None,
        },
        "parameters": {
            "iterations": args.iterations,
            "resolution": args.resolution,
            "eval": args.eval,
            "white_background": args.white_background,
            "extra_arg": args.extra_arg,
        },
        "artifacts": {
            "model_dir_exists": model_dir.exists(),
            "final_iteration_found": final_iteration,
            "final_point_cloud_exists": bool(final_point_cloud and final_point_cloud.exists()),
            "final_point_cloud_size_bytes": (
                final_point_cloud.stat().st_size if final_point_cloud and final_point_cloud.exists() else None
            ),
        },
    }
    metrics_manifest_path = archive_stage_manifest(scene_dir, "train_3dgs", manifest)

    print(f"3DGS model output: {model_dir}")
    print(f"Saved metrics manifest: {metrics_manifest_path}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as exc:
        print(f"[error] Command failed with exit code {exc.returncode}", file=sys.stderr)
        sys.exit(exc.returncode)
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        sys.exit(1)
