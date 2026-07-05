from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from pipeline_manifest import build_command_string, utc_now_iso
from sam2_common import get_data_root, resolve_path_under_root
from evaluate_3dgs_masked_metrics import aggregate_split, find_mask_path, write_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate refined SuGaR renders with full-image and object-masked metrics.",
    )
    parser.add_argument("--scene-dir", required=True, help="Scene directory relative to data/, for example 3dgs/wood_star.")
    parser.add_argument("--sugar-ply", help="Refined SuGaR .ply. Defaults to latest refined_ply under data/sugar_output/<scene>.")
    parser.add_argument("--base-model-dir", help="Base 3DGS model directory relative to data/. Defaults to <scene-dir>/gs/model.")
    parser.add_argument("--source-dir", help="3DGS source directory relative to data/. Defaults to <scene-dir>/gs/source.")
    parser.add_argument("--split", choices=("train", "test", "both"), default="both", help="Camera split to evaluate.")
    parser.add_argument("--masks-dir", default="masks", help="Mask directory inside gs/source. Defaults to masks.")
    parser.add_argument("--crop-padding", type=int, default=8, help="Padding in pixels around the object bbox.")
    parser.add_argument("--white-background", action="store_true", help="Render with white background.")
    parser.add_argument("--output-dir", help="Metrics output directory relative to data/. Defaults to <scene-dir>/metrics/masked_sugar.")
    parser.add_argument("--eval-model-dir", help=argparse.SUPPRESS)
    parser.add_argument("--inside-container", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--refined-checkpoint", help=argparse.SUPPRESS)
    parser.add_argument("--coarse-mesh", help=argparse.SUPPRESS)
    parser.add_argument("--render-dir", help=argparse.SUPPRESS)
    return parser.parse_args()


def scene_name_from_scene_dir(scene_dir_arg: str) -> str:
    return Path(scene_dir_arg).name


def latest_refined_sugar_ply(data_root: Path, scene_name: str) -> Path:
    search_roots = [
        data_root / "sugar_output" / scene_name / "refined_ply",
        *sorted((data_root / "sugar_output").glob(f"{scene_name}_*/refined_ply")),
    ]
    candidates: list[Path] = []
    for root in search_roots:
        if root.is_dir():
            candidates.extend(path for path in root.rglob("*.ply") if path.is_file())
    if not candidates:
        raise FileNotFoundError(f"No refined SuGaR .ply found for scene '{scene_name}' under data/sugar_output.")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def latest_numeric_checkpoint(refined_dir: Path) -> Path:
    candidates: list[tuple[int, Path]] = []
    for path in refined_dir.glob("*.pt"):
        try:
            candidates.append((int(path.stem), path))
        except ValueError:
            continue
    if not candidates:
        raise FileNotFoundError(f"No numeric SuGaR refined checkpoints were found under: {refined_dir}")
    return max(candidates, key=lambda item: item[0])[1]


def infer_sugar_scene_output_dir(sugar_ply: Path) -> Path:
    if sugar_ply.parent.name == "source" and sugar_ply.parent.parent.name == "refined_ply":
        return sugar_ply.parent.parent.parent
    raise ValueError(f"Cannot infer SuGaR output scene directory from: {sugar_ply}")


def coarse_mesh_stem_from_refined_ply(sugar_ply: Path) -> str:
    stem = sugar_ply.stem
    if not stem.startswith("sugarfine_"):
        raise ValueError(f"Unexpected SuGaR refined PLY name: {sugar_ply.name}")
    return "sugarmesh_" + stem.removeprefix("sugarfine_").split("_normalconsistency", 1)[0]


def resolve_sugar_artifacts(sugar_ply: Path) -> tuple[Path, Path]:
    sugar_scene_output_dir = infer_sugar_scene_output_dir(sugar_ply)
    refined_checkpoint = latest_numeric_checkpoint(sugar_scene_output_dir / "refined" / "source" / sugar_ply.stem)
    coarse_mesh = sugar_scene_output_dir / "coarse_mesh" / "source" / f"{coarse_mesh_stem_from_refined_ply(sugar_ply)}.ply"
    if not coarse_mesh.is_file():
        raise FileNotFoundError(f"SuGaR coarse mesh does not exist: {coarse_mesh}")
    return refined_checkpoint, coarse_mesh


def build_sugar_metrics_command(
    args: argparse.Namespace,
    data_root: Path,
    scene_dir: Path,
    source_dir: Path,
    base_model_dir: Path,
    output_dir: Path,
    sugar_ply: Path,
    refined_checkpoint: Path,
    coarse_mesh: Path,
    render_dir: Path,
) -> list[str]:
    scripts_mount = Path(__file__).resolve().parent
    command = [
        "docker",
        "compose",
        "run",
        "--rm",
        "-v",
        f"{scripts_mount}:/app/scripts:ro",
        "sugar",
        "python",
        "/app/scripts/evaluate_sugar_masked_metrics.py",
        "--inside-container",
        "--scene-dir",
        f"/data/{scene_dir.relative_to(data_root).as_posix()}",
        "--source-dir",
        f"/data/{source_dir.relative_to(data_root).as_posix()}",
        "--base-model-dir",
        f"/data/{base_model_dir.relative_to(data_root).as_posix()}",
        "--sugar-ply",
        f"/data/{sugar_ply.relative_to(data_root).as_posix()}",
        "--refined-checkpoint",
        f"/data/{refined_checkpoint.relative_to(data_root).as_posix()}",
        "--coarse-mesh",
        f"/data/{coarse_mesh.relative_to(data_root).as_posix()}",
        "--output-dir",
        f"/data/{output_dir.relative_to(data_root).as_posix()}",
        "--render-dir",
        f"/data/{render_dir.relative_to(data_root).as_posix()}",
        "--split",
        args.split,
        "--masks-dir",
        args.masks_dir,
        "--crop-padding",
        str(args.crop_padding),
    ]
    if args.white_background:
        command.append("--white-background")
    return command


def run_host(args: argparse.Namespace) -> int:
    started_at = utc_now_iso()
    data_root = get_data_root()
    scene_dir = resolve_path_under_root(data_root, args.scene_dir, "scene-dir")
    scene_name = scene_name_from_scene_dir(args.scene_dir)
    source_dir = resolve_path_under_root(data_root, args.source_dir or f"{Path(args.scene_dir).as_posix()}/gs/source", "source-dir")
    base_model_dir = resolve_path_under_root(data_root, args.base_model_dir or f"{Path(args.scene_dir).as_posix()}/gs/model", "base-model-dir")
    sugar_ply = resolve_path_under_root(data_root, args.sugar_ply, "sugar-ply") if args.sugar_ply else latest_refined_sugar_ply(data_root, scene_name)
    output_dir = resolve_path_under_root(data_root, args.output_dir or f"{Path(args.scene_dir).as_posix()}/metrics/masked_sugar", "output-dir")
    render_dir = output_dir / "renders"
    refined_checkpoint, coarse_mesh = resolve_sugar_artifacts(sugar_ply)

    if not (source_dir / "images").is_dir():
        raise FileNotFoundError(f"3DGS source images directory does not exist: {source_dir / 'images'}")
    if not (source_dir / args.masks_dir).is_dir():
        raise FileNotFoundError(f"3DGS masks directory does not exist: {source_dir / args.masks_dir}")
    if not base_model_dir.is_dir():
        raise FileNotFoundError(f"Base 3DGS model directory does not exist: {base_model_dir}")

    command = build_sugar_metrics_command(args, data_root, scene_dir, source_dir, base_model_dir, output_dir, sugar_ply, refined_checkpoint, coarse_mesh, render_dir)
    print("[cmd]", build_command_string(command))
    completed = subprocess.run(command, check=True)

    latest_path = output_dir / "latest.json"
    if latest_path.is_file():
        payload = json.loads(latest_path.read_text(encoding="utf-8"))
        payload.setdefault("host_wrapper", {})
        payload["host_wrapper"].update(
            {
                "started_at": started_at,
                "finished_at": utc_now_iso(),
                "command": build_command_string(command),
            }
        )
        latest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Masked SuGaR metrics: {latest_path}")
    return completed.returncode


def camera_image_name(camera: Any) -> str:
    name = getattr(camera, "image_name", None)
    if name:
        return str(name)
    image_path = getattr(camera, "image_path", None)
    if image_path:
        return Path(str(image_path)).name
    raise ValueError("Could not determine camera image name.")


def render_file_name(image_name: str) -> str:
    path = Path(image_name)
    return path.name if path.suffix else f"{path.name}.png"


def save_render_image(image: Any, path: Path) -> None:
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    array = (image.detach().clamp(0.0, 1.0).cpu().numpy() * 255.0).round().astype("uint8")
    Image.fromarray(array).save(path)


def evaluate_render(rendering: Any, gt: Any, mask_path: Path, crop_padding: int) -> dict[str, Any]:
    import torch
    import torch.nn.functional as F
    from PIL import Image
    from gaussian_splatting.lpipsPyTorch import lpips
    from gaussian_splatting.utils.image_utils import psnr
    from gaussian_splatting.utils.loss_utils import ssim

    mask_image = Image.open(mask_path).convert("L")
    mask = torch.from_numpy(__import__("numpy").array(mask_image, dtype="float32") / 255.0).to("cuda")
    mask = (mask > 0.5).float().unsqueeze(0).unsqueeze(0)
    if mask.shape[-2:] != gt.shape[-2:]:
        mask = F.interpolate(mask, size=gt.shape[-2:], mode="nearest")
    mask_2d = mask[0, 0]
    foreground_pixels = int(mask_2d.sum().detach().cpu())
    total_pixels = int(mask_2d.numel())

    full_l1 = torch.abs(rendering - gt).mean()
    full_metrics = {
        "l1": float(full_l1.detach().cpu()),
        "psnr": float(psnr(rendering.unsqueeze(0), gt.unsqueeze(0)).mean().detach().cpu()),
        "ssim": float(ssim(rendering.unsqueeze(0), gt.unsqueeze(0)).mean().detach().cpu()),
        "lpips": float(lpips(rendering.unsqueeze(0), gt.unsqueeze(0), net_type="vgg").mean().detach().cpu()),
    }

    masked_metrics = None
    bbox = None
    if foreground_pixels > 0:
        mask_3 = mask_2d.unsqueeze(0).expand_as(gt)
        denom = mask_3.sum().clamp_min(1.0)
        masked_l1 = (torch.abs(rendering - gt) * mask_3).sum() / denom
        masked_mse = (((rendering - gt) ** 2) * mask_3).sum() / denom
        masked_psnr = 20 * torch.log10(1.0 / torch.sqrt(masked_mse.clamp_min(1e-12)))
        ys, xs = torch.nonzero(mask_2d > 0.5, as_tuple=True)
        padding = max(0, int(crop_padding))
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

    return {
        "mask_path": str(mask_path),
        "mask_foreground_pixels": foreground_pixels,
        "mask_coverage": foreground_pixels / total_pixels if total_pixels else None,
        "object_bbox": bbox,
        "full_image": full_metrics,
        "masked_object": masked_metrics,
    }


def run_inside_container(args: argparse.Namespace) -> int:
    import os

    os.chdir("/opt/SuGaR")
    sys.path.insert(0, "/opt/SuGaR")
    sys.path.insert(0, "/app/scripts")

    import open3d as o3d
    import torch
    from sugar_scene.gs_model import GaussianSplattingWrapper
    from sugar_scene.sugar_model import SuGaR
    from sugar_utils.spherical_harmonics import SH2RGB

    source_dir = Path(args.source_dir or args.scene_dir).resolve()
    base_model_dir = Path(args.base_model_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    sugar_ply = Path(args.sugar_ply).resolve()
    refined_checkpoint = Path(args.refined_checkpoint).resolve()
    coarse_mesh = Path(args.coarse_mesh).resolve()
    render_dir = Path(args.render_dir).resolve()
    requested_splits = ["train", "test"] if args.split == "both" else [args.split]
    eval_split_requested = "test" in requested_splits

    started = time.time()
    started_at = utc_now_iso()
    torch.cuda.set_device(0)
    nerfmodel_30k = GaussianSplattingWrapper(
        source_path=str(source_dir),
        output_path=str(base_model_dir),
        iteration_to_load=30000,
        load_gt_images=True,
        eval_split=eval_split_requested,
        eval_split_interval=8,
        white_background=args.white_background,
    )
    checkpoint = torch.load(refined_checkpoint, map_location=nerfmodel_30k.device)
    n_gaussians_per_triangle = int(sugar_ply.stem.rsplit("gaussperface", 1)[1]) if "gaussperface" in sugar_ply.stem else 1
    refined_sugar = SuGaR(
        nerfmodel=nerfmodel_30k,
        points=checkpoint["state_dict"]["_points"],
        colors=SH2RGB(checkpoint["state_dict"]["_sh_coordinates_dc"][:, 0, :]),
        initialize=False,
        sh_levels=nerfmodel_30k.gaussians.active_sh_degree + 1,
        keep_track_of_knn=False,
        knn_to_track=0,
        beta_mode="average",
        surface_mesh_to_bind=o3d.io.read_triangle_mesh(str(coarse_mesh)),
        n_gaussians_per_surface_triangle=n_gaussians_per_triangle,
    )
    refined_sugar.load_state_dict(checkpoint["state_dict"])
    refined_sugar.eval()
    sh_deg_to_use = nerfmodel_30k.gaussians.active_sh_degree
    bg_color = torch.tensor([1.0, 1.0, 1.0] if args.white_background else [0.0, 0.0, 0.0], device=nerfmodel_30k.device)

    split_sources = {
        "train": (nerfmodel_30k.training_cameras, nerfmodel_30k.cam_list, nerfmodel_30k.get_gt_image),
        "test": (nerfmodel_30k.test_cameras, nerfmodel_30k.test_cam_list, nerfmodel_30k.get_test_gt_image),
    }
    frames: list[dict[str, Any]] = []
    with torch.no_grad():
        for split in requested_splits:
            nerf_cameras, cameras, gt_getter = split_sources[split]
            if nerf_cameras is None or cameras is None:
                continue
            for camera_index, camera in enumerate(cameras):
                image_name = camera_image_name(camera)
                rendering = refined_sugar.render_image_gaussian_rasterizer(
                    nerf_cameras=nerf_cameras,
                    camera_indices=camera_index,
                    verbose=False,
                    bg_color=bg_color,
                    sh_deg=sh_deg_to_use,
                    compute_color_in_rasterizer=True,
                ).clamp(min=0, max=1).permute(2, 0, 1)
                gt = gt_getter(camera_index, to_cuda=True).permute(2, 0, 1).clamp(0.0, 1.0)
                mask_path = find_mask_path(source_dir, args.masks_dir, image_name)
                render_path = render_dir / split / render_file_name(image_name)
                save_render_image(rendering.permute(1, 2, 0), render_path)
                frame = evaluate_render(rendering, gt, mask_path, args.crop_padding)
                frame.update({"split": split, "image_name": image_name, "render_path": str(render_path)})
                frames.append(frame)

    splits = {
        split: aggregate_split([frame for frame in frames if frame["split"] == split])
        for split in requested_splits
        if any(frame["split"] == split for frame in frames)
    }
    preferred_split = "test" if "test" in splits else "train" if "train" in splits else None
    report = {
        "status": "success",
        "started_at": started_at,
        "finished_at": utc_now_iso(),
        "duration_seconds": round(time.time() - started, 3),
        "metric_type": "masked_sugar",
        "scene_dir": str(Path(args.scene_dir)),
        "input_paths": {
            "source_dir": str(source_dir),
            "sugar_ply": str(sugar_ply),
            "refined_checkpoint": str(refined_checkpoint),
            "coarse_mesh": str(coarse_mesh),
            "base_model_dir": str(base_model_dir),
            "masks_dir": str(source_dir / args.masks_dir),
            "render_dir": str(render_dir),
        },
        "parameters": {
            "split": args.split,
            "preferred_split": preferred_split,
            "eval_split_requested": eval_split_requested,
            "masks_dir": args.masks_dir,
            "crop_padding": args.crop_padding,
            "white_background": args.white_background,
        },
        "metrics": {"preferred_split": preferred_split, "splits": splits},
        "frames": frames,
        "artifacts": {"frame_count": len(frames), "split_count": len(splits)},
    }
    report_path = write_report(output_dir, report)
    print(f"Saved masked SuGaR metrics: {report_path}")
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
