from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline_manifest import archive_stage_manifest, build_command_string, utc_now_iso
from sam2_common import get_data_root, resolve_path_under_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate 3DGS renders with full-image and object-masked metrics.",
    )
    parser.add_argument("--scene-dir", required=True, help="Scene directory relative to data/, for example 3dgs/wood_star.")
    parser.add_argument("--model-dir", help="3DGS model directory relative to data/. Defaults to <scene-dir>/gs/model.")
    parser.add_argument("--iteration", type=int, help="3DGS iteration to evaluate. Defaults to latest available.")
    parser.add_argument("--masks-dir", default="masks", help="Mask directory inside gs/source. Defaults to masks.")
    parser.add_argument("--split", choices=("train", "test", "both"), default="both", help="Camera split to evaluate.")
    parser.add_argument("--crop-padding", type=int, default=8, help="Padding in pixels around the object bbox for masked SSIM/LPIPS.")
    parser.add_argument("--white-background", action="store_true", help="Render with white background.")
    parser.add_argument("--output-dir", help="Metrics output directory relative to data/. Defaults to <scene-dir>/metrics/masked_3dgs.")
    parser.add_argument("--inside-container", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--source-dir", help=argparse.SUPPRESS)
    return parser.parse_args()


def latest_iteration(model_dir: Path) -> int:
    point_cloud_root = model_dir / "point_cloud"
    if not point_cloud_root.is_dir():
        raise FileNotFoundError(f"3DGS point_cloud directory not found: {point_cloud_root}")
    iterations: list[int] = []
    for path in point_cloud_root.iterdir():
        if not path.is_dir() or not path.name.startswith("iteration_"):
            continue
        try:
            iteration = int(path.name.split("_", 1)[1])
        except ValueError:
            continue
        if (path / "point_cloud.ply").is_file():
            iterations.append(iteration)
    if not iterations:
        raise FileNotFoundError(f"No point_cloud.ply iterations found under {point_cloud_root}")
    return max(iterations)


def mean_or_none(values: list[float | None]) -> float | None:
    usable = [value for value in values if value is not None and math.isfinite(value)]
    return sum(usable) / len(usable) if usable else None


def aggregate_metric_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    metric_names = ("l1", "psnr", "ssim", "lpips")
    return {name: mean_or_none([record.get(name) for record in records]) for name in metric_names}


def aggregate_split(frames: list[dict[str, Any]]) -> dict[str, Any]:
    full_records = [frame["full_image"] for frame in frames]
    masked_records = [frame["masked_object"] for frame in frames if frame.get("masked_object") is not None]
    return {
        "frame_count": len(frames),
        "masked_frame_count": len(masked_records),
        "mean_mask_coverage": mean_or_none([frame.get("mask_coverage") for frame in frames]),
        "full_image": aggregate_metric_records(full_records),
        "masked_object": aggregate_metric_records(masked_records),
    }


def write_report(output_dir: Path, report: dict[str, Any]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    report_path = output_dir / f"{timestamp}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    shutil.copyfile(report_path, output_dir / "latest.json")
    return report_path


def run_host(args: argparse.Namespace) -> int:
    started = time.time()
    started_at = utc_now_iso()
    data_root = get_data_root()
    scene_dir = resolve_path_under_root(data_root, args.scene_dir, "scene-dir")
    source_dir = scene_dir / "gs" / "source"
    model_dir = resolve_path_under_root(
        data_root,
        args.model_dir or f"{Path(args.scene_dir).as_posix()}/gs/model",
        "model-dir",
    )
    masks_dir = source_dir / args.masks_dir
    output_dir = resolve_path_under_root(
        data_root,
        args.output_dir or f"{Path(args.scene_dir).as_posix()}/metrics/masked_3dgs",
        "output-dir",
    )

    if not source_dir.is_dir():
        raise FileNotFoundError(f"3DGS source dataset does not exist: {source_dir}")
    if not (source_dir / "images").is_dir():
        raise FileNotFoundError(f"3DGS source images directory does not exist: {source_dir / 'images'}")
    if not masks_dir.is_dir():
        raise FileNotFoundError(f"3DGS masks directory does not exist: {masks_dir}")
    if not model_dir.is_dir():
        raise FileNotFoundError(f"3DGS model directory does not exist: {model_dir}")

    iteration = args.iteration or latest_iteration(model_dir)
    scripts_mount = Path(__file__).resolve().parent
    command = [
        "docker",
        "compose",
        "run",
        "--rm",
        "-v",
        f"{scripts_mount}:/app/scripts:ro",
        "gaussian-splatting",
        "python",
        "/app/scripts/evaluate_3dgs_masked_metrics.py",
        "--inside-container",
        "--scene-dir",
        f"/data/{scene_dir.relative_to(data_root).as_posix()}",
        "--source-dir",
        f"/data/{source_dir.relative_to(data_root).as_posix()}",
        "--model-dir",
        f"/data/{model_dir.relative_to(data_root).as_posix()}",
        "--output-dir",
        f"/data/{output_dir.relative_to(data_root).as_posix()}",
        "--iteration",
        str(iteration),
        "--masks-dir",
        args.masks_dir,
        "--split",
        args.split,
        "--crop-padding",
        str(args.crop_padding),
    ]
    if args.white_background:
        command.append("--white-background")

    print("[cmd]", build_command_string(command))
    completed = subprocess.run(command, check=True)
    finished_at = utc_now_iso()

    latest_path = output_dir / "latest.json"
    if latest_path.is_file():
        payload = json.loads(latest_path.read_text(encoding="utf-8"))
        payload.setdefault("host_wrapper", {})
        payload["host_wrapper"].update(
            {
                "started_at": started_at,
                "finished_at": finished_at,
                "duration_seconds": round(time.time() - started, 3),
                "command": build_command_string(command),
            }
        )
        latest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Masked 3DGS metrics: {latest_path}")
    return completed.returncode


def find_mask_path(source_dir: Path, masks_dir: str, image_name: str) -> Path:
    masks_root = source_dir / masks_dir
    candidates = [masks_root / image_name]
    stem = Path(image_name).stem
    candidates.extend(masks_root / f"{stem}{suffix}" for suffix in (".png", ".jpg", ".jpeg"))
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Mask for image '{image_name}' was not found under {masks_root}")


def run_inside_container(args: argparse.Namespace) -> int:
    sys.path.insert(0, "/opt/gaussian-splatting")

    import torch
    import torch.nn.functional as F
    from PIL import Image
    from argparse import ArgumentParser
    from arguments import ModelParams, PipelineParams, get_combined_args
    from gaussian_renderer import GaussianModel, render
    from lpipsPyTorch import lpips
    from scene import Scene
    from utils.image_utils import psnr
    from utils.loss_utils import ssim

    try:
        from diff_gaussian_rasterization import SparseGaussianAdam
        separate_sh = True
    except Exception:
        separate_sh = False

    source_dir = Path(args.source_dir or args.scene_dir).resolve()
    model_dir = Path(args.model_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    requested_splits = ["train", "test"] if args.split == "both" else [args.split]
    eval_split_requested = "test" in requested_splits

    official_parser = ArgumentParser(description="3DGS masked metrics internal parser")
    model_params = ModelParams(official_parser, sentinel=True)
    pipeline_params = PipelineParams(official_parser)
    official_argv = [
        "masked_metrics",
        "-s",
        str(source_dir),
        "-m",
        str(model_dir),
        "--masks",
        args.masks_dir,
    ]
    if eval_split_requested:
        official_argv.append("--eval")
    if args.white_background:
        official_argv.append("--white_background")
    old_argv = sys.argv
    try:
        sys.argv = official_argv
        official_args = get_combined_args(official_parser)
    finally:
        sys.argv = old_argv

    official_args.masks = args.masks_dir
    official_args.eval = eval_split_requested
    official_args.white_background = args.white_background
    dataset = model_params.extract(official_args)
    pipeline = pipeline_params.extract(official_args)

    started = time.time()
    started_at = utc_now_iso()
    with torch.no_grad():
        gaussians = GaussianModel(dataset.sh_degree)
        scene = Scene(dataset, gaussians, load_iteration=args.iteration, shuffle=False)
        background = torch.tensor([1, 1, 1] if dataset.white_background else [0, 0, 0], dtype=torch.float32, device="cuda")

        split_views = {
            "train": scene.getTrainCameras(),
            "test": scene.getTestCameras(),
        }
        frames: list[dict[str, Any]] = []
        for split in requested_splits:
            views = split_views.get(split) or []
            if not views:
                continue
            for view in views:
                rendering = render(view, gaussians, pipeline, background, separate_sh=separate_sh)["render"].clamp(0.0, 1.0)
                gt = view.original_image[0:3, :, :].cuda().clamp(0.0, 1.0)
                if getattr(dataset, "train_test_exp", False):
                    rendering = rendering[..., rendering.shape[-1] // 2:]
                    gt = gt[..., gt.shape[-1] // 2:]

                full_l1 = torch.abs(rendering - gt).mean()
                full_metrics = {
                    "l1": float(full_l1.detach().cpu()),
                    "psnr": float(psnr(rendering.unsqueeze(0), gt.unsqueeze(0)).mean().detach().cpu()),
                    "ssim": float(ssim(rendering.unsqueeze(0), gt.unsqueeze(0)).mean().detach().cpu()),
                    "lpips": float(lpips(rendering.unsqueeze(0), gt.unsqueeze(0), net_type="vgg").mean().detach().cpu()),
                }

                mask_path = find_mask_path(source_dir, args.masks_dir, view.image_name)
                mask_image = Image.open(mask_path).convert("L")
                mask = torch.from_numpy(__import__("numpy").array(mask_image, dtype="float32") / 255.0).to("cuda")
                mask = (mask > 0.5).float().unsqueeze(0).unsqueeze(0)
                if mask.shape[-2:] != gt.shape[-2:]:
                    mask = F.interpolate(mask, size=gt.shape[-2:], mode="nearest")
                mask_2d = mask[0, 0]
                foreground_pixels = int(mask_2d.sum().detach().cpu())
                total_pixels = int(mask_2d.numel())
                masked_metrics = None
                bbox = None
                if foreground_pixels > 0:
                    mask_3 = mask_2d.unsqueeze(0).expand_as(gt)
                    denom = mask_3.sum().clamp_min(1.0)
                    masked_l1 = (torch.abs(rendering - gt) * mask_3).sum() / denom
                    masked_mse = (((rendering - gt) ** 2) * mask_3).sum() / denom
                    masked_psnr = 20 * torch.log10(1.0 / torch.sqrt(masked_mse.clamp_min(1e-12)))

                    ys, xs = torch.nonzero(mask_2d > 0.5, as_tuple=True)
                    padding = max(0, int(args.crop_padding))
                    y0 = max(int(ys.min().item()) - padding, 0)
                    y1 = min(int(ys.max().item()) + padding + 1, gt.shape[-2])
                    x0 = max(int(xs.min().item()) - padding, 0)
                    x1 = min(int(xs.max().item()) + padding + 1, gt.shape[-1])
                    bbox = {"x0": x0, "y0": y0, "x1": x1, "y1": y1}
                    crop_mask = mask_2d[y0:y1, x0:x1].unsqueeze(0)
                    render_crop = rendering[:, y0:y1, x0:x1] * crop_mask
                    gt_crop = gt[:, y0:y1, x0:x1] * crop_mask
                    masked_metrics = {
                        "l1": float(masked_l1.detach().cpu()),
                        "psnr": float(masked_psnr.detach().cpu()),
                        "ssim": float(ssim(render_crop.unsqueeze(0), gt_crop.unsqueeze(0)).mean().detach().cpu()),
                        "lpips": float(lpips(render_crop.unsqueeze(0), gt_crop.unsqueeze(0), net_type="vgg").mean().detach().cpu()),
                    }

                frames.append(
                    {
                        "split": split,
                        "image_name": view.image_name,
                        "mask_path": str(mask_path),
                        "mask_foreground_pixels": foreground_pixels,
                        "mask_coverage": foreground_pixels / total_pixels if total_pixels else None,
                        "object_bbox": bbox,
                        "full_image": full_metrics,
                        "masked_object": masked_metrics,
                    }
                )

    splits = {split: aggregate_split([frame for frame in frames if frame["split"] == split]) for split in requested_splits if any(frame["split"] == split for frame in frames)}
    preferred_split = "test" if "test" in splits else "train" if "train" in splits else None
    finished_at = utc_now_iso()
    report = {
        "status": "success",
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": round(time.time() - started, 3),
        "scene_dir": str(Path(args.scene_dir)),
        "input_paths": {
            "source_dir": str(source_dir),
            "model_dir": str(model_dir),
            "masks_dir": str(source_dir / args.masks_dir),
        },
        "parameters": {
            "iteration": args.iteration,
            "split": args.split,
            "preferred_split": preferred_split,
            "eval_split_requested": eval_split_requested,
            "masks_dir": args.masks_dir,
            "crop_padding": args.crop_padding,
            "white_background": args.white_background,
        },
        "metrics": {
            "preferred_split": preferred_split,
            "splits": splits,
        },
        "frames": frames,
        "artifacts": {
            "frame_count": len(frames),
            "split_count": len(splits),
        },
    }
    report_path = write_report(output_dir, report)
    print(f"Saved masked 3DGS metrics: {report_path}")
    return 0


def main() -> int:
    args = parse_args()
    if args.crop_padding < 0:
        raise ValueError("crop-padding must be >= 0")
    if args.inside_container:
        return run_inside_container(args)
    return run_host(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"[error] Command failed with exit code {exc.returncode}", file=sys.stderr)
        raise SystemExit(exc.returncode)
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        raise SystemExit(1)
