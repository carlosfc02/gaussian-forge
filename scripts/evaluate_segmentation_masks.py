from __future__ import annotations

import argparse
import json
import math
import shutil
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from sam2_common import get_data_root, resolve_path_under_root

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}
METRIC_NAMES = (
    "iou",
    "dice",
    "precision",
    "recall",
    "specificity",
    "accuracy",
    "boundary_precision",
    "boundary_recall",
    "boundary_f1",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare SAM2 masks with ground-truth masks and write segmentation metrics.",
    )
    parser.add_argument("--scene-name", required=True, help="Scene name, for example pillow.")
    parser.add_argument(
        "--pred-dir",
        help="Predicted mask directory relative to data/. Defaults to masks/<scene-name>.",
    )
    parser.add_argument(
        "--gt-dir",
        help="Ground-truth mask directory relative to data/. Defaults to GT/<scene-name>/masks_gt.",
    )
    parser.add_argument(
        "--output-dir",
        help="Metrics directory relative to data/. Defaults to metrics/segmentation/<scene-name>.",
    )
    parser.add_argument(
        "--gt-frame-offset",
        default="auto",
        help=(
            "GT index minus prediction index. Use an integer or 'auto'. "
            "For pillow, auto detects +1 because SAM2 starts at frame 0 and UCO3D at frame 1."
        ),
    )
    parser.add_argument(
        "--offset-search-radius",
        type=int,
        default=10,
        help="Offsets searched in auto mode. Defaults to 10.",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=127,
        help="Pixels greater than this value are foreground. Defaults to 127.",
    )
    parser.add_argument(
        "--boundary-tolerance",
        type=float,
        default=0.008,
        help=(
            "Boundary matching tolerance. Values below 1 are a fraction of the image diagonal; "
            "values >= 1 are pixels. Defaults to 0.008."
        ),
    )
    parser.add_argument(
        "--resize-gt",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Resize GT masks with nearest-neighbor when dimensions differ. Defaults to false.",
    )
    parser.add_argument(
        "--save-latest",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Also update latest.json in the output directory. Defaults to true.",
    )
    return parser.parse_args()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_offset(value: str) -> int | None:
    if value.lower() == "auto":
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError("gt-frame-offset must be an integer or 'auto'") from exc


def indexed_images(directory: Path) -> dict[int, Path]:
    if not directory.exists():
        raise FileNotFoundError(f"Mask directory does not exist: {directory}")
    images: dict[int, Path] = {}
    for path in directory.iterdir():
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        try:
            frame_index = int(path.stem)
        except ValueError:
            continue
        if frame_index in images:
            raise ValueError(f"Duplicate mask index {frame_index} in {directory}")
        images[frame_index] = path
    if not images:
        raise FileNotFoundError(f"No numerically named mask images found in {directory}")
    return images


def detect_gt_offset(pred_indices: set[int], gt_indices: set[int], radius: int) -> tuple[int, dict[int, int]]:
    if radius < 0:
        raise ValueError("offset-search-radius must be >= 0")
    match_counts = {
        offset: sum((index + offset) in gt_indices for index in pred_indices)
        for offset in range(-radius, radius + 1)
    }
    best_offset = max(match_counts, key=lambda offset: (match_counts[offset], -abs(offset), offset == 0))
    if match_counts[best_offset] == 0:
        raise ValueError("Could not match any prediction frame with a GT frame in the offset search range")
    return best_offset, match_counts


def load_binary_mask(path: Path, threshold: int) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"Could not read mask image: {path}")
    return image > threshold


def safe_ratio(numerator: int, denominator: int, empty_value: float) -> float:
    return float(numerator / denominator) if denominator else empty_value


def mask_boundary(mask: np.ndarray) -> np.ndarray:
    if not mask.any():
        return np.zeros(mask.shape, dtype=bool)
    mask_u8 = mask.astype(np.uint8)
    eroded = cv2.erode(mask_u8, np.ones((3, 3), dtype=np.uint8), iterations=1)
    return mask & ~eroded.astype(bool)


def boundary_metrics(pred: np.ndarray, gt: np.ndarray, tolerance: float) -> tuple[float, float, float, int]:
    pred_boundary = mask_boundary(pred)
    gt_boundary = mask_boundary(gt)
    pred_count = int(pred_boundary.sum())
    gt_count = int(gt_boundary.sum())
    if pred_count == 0 and gt_count == 0:
        return 1.0, 1.0, 1.0, 0
    if tolerance < 1:
        tolerance_pixels = max(1, int(math.ceil(tolerance * math.hypot(*pred.shape))))
    else:
        tolerance_pixels = max(1, int(round(tolerance)))
    distance_to_gt = cv2.distanceTransform((~gt_boundary).astype(np.uint8), cv2.DIST_L2, 3)
    distance_to_pred = cv2.distanceTransform((~pred_boundary).astype(np.uint8), cv2.DIST_L2, 3)
    pred_matches = int(np.logical_and(pred_boundary, distance_to_gt <= tolerance_pixels).sum())
    gt_matches = int(np.logical_and(gt_boundary, distance_to_pred <= tolerance_pixels).sum())
    precision = safe_ratio(pred_matches, pred_count, 0.0)
    recall = safe_ratio(gt_matches, gt_count, 0.0)
    f1 = safe_ratio(2 * precision * recall, precision + recall, 0.0)
    return precision, recall, f1, tolerance_pixels


def evaluate_pair(pred: np.ndarray, gt: np.ndarray, boundary_tolerance: float) -> dict[str, Any]:
    tp = int(np.logical_and(pred, gt).sum())
    fp = int(np.logical_and(pred, ~gt).sum())
    fn = int(np.logical_and(~pred, gt).sum())
    tn = int(np.logical_and(~pred, ~gt).sum())
    both_empty = tp + fp + fn == 0
    precision = safe_ratio(tp, tp + fp, 1.0 if both_empty else 0.0)
    recall = safe_ratio(tp, tp + fn, 1.0 if both_empty else 0.0)
    boundary_precision, boundary_recall, boundary_f1, tolerance_pixels = boundary_metrics(
        pred, gt, boundary_tolerance
    )
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "pred_foreground_pixels": int(pred.sum()),
        "gt_foreground_pixels": int(gt.sum()),
        "iou": safe_ratio(tp, tp + fp + fn, 1.0),
        "dice": safe_ratio(2 * tp, 2 * tp + fp + fn, 1.0),
        "precision": precision,
        "recall": recall,
        "specificity": safe_ratio(tn, tn + fp, 1.0),
        "accuracy": safe_ratio(tp + tn, tp + tn + fp + fn, 1.0),
        "boundary_precision": boundary_precision,
        "boundary_recall": boundary_recall,
        "boundary_f1": boundary_f1,
        "boundary_tolerance_pixels": tolerance_pixels,
    }


def aggregate_macro(frames: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for name in METRIC_NAMES:
        values = [float(frame["metrics"][name]) for frame in frames]
        result[name] = {
            "mean": statistics.fmean(values),
            "std": statistics.pstdev(values),
            "min": min(values),
            "max": max(values),
        }
    return result


def aggregate_micro(frames: list[dict[str, Any]]) -> dict[str, float | int]:
    tp = sum(frame["metrics"]["tp"] for frame in frames)
    fp = sum(frame["metrics"]["fp"] for frame in frames)
    fn = sum(frame["metrics"]["fn"] for frame in frames)
    tn = sum(frame["metrics"]["tn"] for frame in frames)
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "iou": safe_ratio(tp, tp + fp + fn, 1.0),
        "dice": safe_ratio(2 * tp, 2 * tp + fp + fn, 1.0),
        "precision": safe_ratio(tp, tp + fp, 1.0),
        "recall": safe_ratio(tp, tp + fn, 1.0),
        "specificity": safe_ratio(tn, tn + fp, 1.0),
        "accuracy": safe_ratio(tp + tn, tp + tn + fp + fn, 1.0),
    }


def main() -> int:
    args = parse_args()
    if not 0 <= args.threshold <= 255:
        raise ValueError("threshold must be between 0 and 255")
    if args.boundary_tolerance <= 0:
        raise ValueError("boundary-tolerance must be > 0")

    started = time.time()
    started_at = utc_now_iso()
    data_root = get_data_root()
    pred_dir = resolve_path_under_root(data_root, args.pred_dir or f"masks/{args.scene_name}", "pred-dir")
    gt_dir = resolve_path_under_root(data_root, args.gt_dir or f"GT/{args.scene_name}/masks_gt", "gt-dir")
    output_dir = resolve_path_under_root(data_root, args.output_dir or f"metrics/segmentation/{args.scene_name}", "output-dir")
    pred_images = indexed_images(pred_dir)
    gt_images = indexed_images(gt_dir)

    requested_offset = parse_offset(args.gt_frame_offset)
    offset_scores: dict[int, int] | None = None
    if requested_offset is None:
        gt_offset, offset_scores = detect_gt_offset(set(pred_images), set(gt_images), args.offset_search_radius)
    else:
        gt_offset = requested_offset

    matched_indices = sorted(index for index in pred_images if index + gt_offset in gt_images)
    if not matched_indices:
        raise ValueError(f"No matched masks using GT frame offset {gt_offset:+d}")

    frames: list[dict[str, Any]] = []
    resized_frames: list[int] = []
    expected_shape: tuple[int, int] | None = None
    for position, pred_index in enumerate(matched_indices, start=1):
        gt_index = pred_index + gt_offset
        pred_path = pred_images[pred_index]
        gt_path = gt_images[gt_index]
        pred = load_binary_mask(pred_path, args.threshold)
        gt = load_binary_mask(gt_path, args.threshold)
        if pred.shape != gt.shape:
            if not args.resize_gt:
                raise ValueError(
                    f"Mask shape mismatch for prediction {pred_index} and GT {gt_index}: "
                    f"{pred.shape} != {gt.shape}. Pass --resize-gt to resize GT with nearest-neighbor."
                )
            gt = cv2.resize(gt.astype(np.uint8), (pred.shape[1], pred.shape[0]), interpolation=cv2.INTER_NEAREST).astype(bool)
            resized_frames.append(pred_index)
        if expected_shape is None:
            expected_shape = pred.shape
        metrics = evaluate_pair(pred, gt, args.boundary_tolerance)
        frames.append({
            "prediction_frame_index": pred_index,
            "gt_frame_index": gt_index,
            "prediction_path": pred_path.relative_to(data_root).as_posix(),
            "gt_path": gt_path.relative_to(data_root).as_posix(),
            "width": int(pred.shape[1]),
            "height": int(pred.shape[0]),
            "metrics": metrics,
        })
        if position == 1 or position % 25 == 0 or position == len(matched_indices):
            print(f"[{position}/{len(matched_indices)}] frame {pred_index} -> GT {gt_index}: IoU={metrics['iou']:.6f}, Dice={metrics['dice']:.6f}")

    finished_at = utc_now_iso()
    macro_metrics = aggregate_macro(frames)
    micro_metrics = aggregate_micro(frames)
    report = {
        "status": "success",
        "scene_name": args.scene_name,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": round(time.time() - started, 3),
        "prediction_dir": pred_dir.relative_to(data_root).as_posix(),
        "gt_dir": gt_dir.relative_to(data_root).as_posix(),
        "configuration": {
            "threshold": args.threshold,
            "gt_frame_offset": gt_offset,
            "gt_frame_offset_mode": "auto" if requested_offset is None else "manual",
            "offset_search_radius": args.offset_search_radius if requested_offset is None else None,
            "offset_match_counts": {str(key): value for key, value in sorted((offset_scores or {}).items())},
            "boundary_tolerance": args.boundary_tolerance,
            "resize_gt": args.resize_gt,
        },
        "coverage": {
            "prediction_count": len(pred_images),
            "gt_count": len(gt_images),
            "matched_count": len(frames),
            "unmatched_prediction_indices": sorted(set(pred_images) - set(matched_indices)),
            "unused_gt_indices": sorted(set(gt_images) - {index + gt_offset for index in matched_indices}),
            "resized_prediction_indices": resized_frames,
        },
        "image_shape": {"height": expected_shape[0], "width": expected_shape[1]} if expected_shape else None,
        "aggregate": {
            "macro": macro_metrics,
            "micro": micro_metrics,
            "j_and_f": statistics.fmean([
                macro_metrics["iou"]["mean"],
                macro_metrics["boundary_f1"]["mean"],
            ]),
        },
        "frames": frames,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    report_path = output_dir / f"{timestamp}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.save_latest:
        shutil.copyfile(report_path, output_dir / "latest.json")

    macro = report["aggregate"]["macro"]
    print(f"GT frame offset: {gt_offset:+d}")
    print(f"Matched masks: {len(frames)}/{len(pred_images)} predictions")
    print(f"Mean IoU: {macro['iou']['mean']:.6f}")
    print(f"Mean Dice: {macro['dice']['mean']:.6f}")
    print(f"Mean boundary F1: {macro['boundary_f1']['mean']:.6f}")
    print(f"J&F: {report['aggregate']['j_and_f']:.6f}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())