from __future__ import annotations

import argparse
import re
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
        "--mask-loss",
        action="store_true",
        help="Enable object mask weighting for the 3DGS RGB/SSIM photometric loss.",
    )
    parser.add_argument(
        "--masks-dir",
        default="masks",
        help="Mask directory inside the 3DGS source dataset. Defaults to masks.",
    )
    parser.add_argument(
        "--log-path",
        help="Optional path where combined 3DGS stdout/stderr will be written.",
    )
    parser.add_argument(
        "--extra-arg",
        action="append",
        default=[],
        help="Extra argument passed through to train.py. Repeatable.",
    )
    return parser.parse_args()


def run_command(command: list[str], log_path: Path | None = None) -> str:
    print("[cmd]", shlex.join(command))
    if log_path is None:
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
        output = "\n".join(part for part in [completed.stdout, completed.stderr] if part)
        if output:
            print(output, end="" if output.endswith("\n") else "\n")
        return output

    output_parts: list[str] = []
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8", errors="replace") as log_handle:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="")
            log_handle.write(line)
            output_parts.append(line)
        return_code = process.wait()

    if return_code != 0:
        raise subprocess.CalledProcessError(return_code, command)
    return "".join(output_parts)


def parse_eval_metrics(output: str) -> list[dict[str, float | int | str | None]]:
    pattern = re.compile(
        r"\[ITER\s+(?P<iteration>\d+)\]\s+Evaluating\s+(?P<split>\w+):\s+"
        r"L1\s+(?P<l1>[-+0-9.eE]+)\s+PSNR\s+(?P<psnr>[-+0-9.eE]+)"
        r"(?:\s+SSIM\s+(?P<ssim>[-+0-9.eE]+))?"
    )
    metrics = []
    for match in pattern.finditer(output):
        metrics.append(
            {
                "iteration": int(match.group("iteration")),
                "split": match.group("split"),
                "l1": float(match.group("l1")),
                "psnr": float(match.group("psnr")),
                "ssim": float(match.group("ssim")) if match.group("ssim") is not None else None,
            }
        )
    return metrics


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
    if args.mask_loss and not (source_dir / args.masks_dir).exists():
        raise FileNotFoundError(
            f"3DGS mask loss was requested but masks directory does not exist: {source_dir / args.masks_dir}"
        )

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
    if args.mask_loss:
        command.extend(["--mask_loss", "--masks", args.masks_dir])
    command.extend(args.extra_arg)

    log_path = Path(args.log_path).resolve() if args.log_path else model_dir / "train_3dgs.log"
    command_output = run_command(command, log_path)
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
            "mask_loss": args.mask_loss,
            "masks_dir": args.masks_dir,
            "log_path": str(log_path),
            "extra_arg": args.extra_arg,
        },
        "metrics_3dgs": parse_eval_metrics(command_output),
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
