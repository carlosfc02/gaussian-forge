from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from pathlib import Path

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


def main() -> int:
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
    print(f"3DGS model output: {model_dir}")
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
