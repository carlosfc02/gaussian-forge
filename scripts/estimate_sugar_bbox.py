from __future__ import annotations

import argparse
import json
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from sam2_common import get_data_root, resolve_path_under_root


@dataclass
class ImageRecord:
    image_id: int
    name: str
    xys: np.ndarray


@dataclass
class Point3DRecord:
    point3d_id: int
    xyz: np.ndarray
    track: list[tuple[int, int]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Estimate a SuGaR 3D foreground bounding box from COLMAP sparse points and SAM 2 masks.",
    )
    parser.add_argument(
        "--scene-dir",
        required=True,
        help="Scene directory relative to data/, for example 3dgs/wood_star.",
    )
    parser.add_argument(
        "--sparse-model",
        type=int,
        help="Optional COLMAP sparse model id under colmap/sparse/. Defaults to auto-selecting the best available model.",
    )
    parser.add_argument(
        "--masks-dir",
        help="Optional masks directory relative to data/. Defaults to <scene-dir>/colmap/masks.",
    )
    parser.add_argument(
        "--min-observations",
        type=int,
        default=2,
        help="Minimum valid track observations required to consider a point. Defaults to 2.",
    )
    parser.add_argument(
        "--min-foreground-ratio",
        type=float,
        default=0.6,
        help="Minimum fraction of mask-positive observations required to keep a point. Defaults to 0.6.",
    )
    parser.add_argument(
        "--lower-percentile",
        type=float,
        default=1.0,
        help="Lower percentile used to trim sparse outliers before computing bboxmin. Defaults to 1.0.",
    )
    parser.add_argument(
        "--upper-percentile",
        type=float,
        default=99.0,
        help="Upper percentile used to trim sparse outliers before computing bboxmax. Defaults to 99.0.",
    )
    parser.add_argument(
        "--padding-scale",
        type=float,
        default=0.05,
        help="Relative padding applied to the trimmed box extent. Defaults to 0.05.",
    )
    parser.add_argument(
        "--min-padding",
        type=float,
        default=0.0,
        help="Minimum absolute padding applied per axis. Defaults to 0.0.",
    )
    parser.add_argument(
        "--erode-pixels",
        type=int,
        default=0,
        help="Optional mask erosion in pixels before testing observations. Defaults to 0.",
    )
    parser.add_argument(
        "--output-json",
        help="Optional output JSON path relative to data/. Defaults to <scene-dir>/sugar_bbox_estimate.json.",
    )
    return parser.parse_args()


def read_next_bytes(fid, num_bytes: int, format_sequence: str):
    data = fid.read(num_bytes)
    if len(data) != num_bytes:
        raise EOFError("Unexpected end of file while reading COLMAP binary model.")
    return struct.unpack("<" + format_sequence, data)


def read_num_records(path: Path) -> int:
    with path.open("rb") as handle:
        return int(read_next_bytes(handle, 8, "Q")[0])


def read_images_binary(path: Path) -> dict[int, ImageRecord]:
    images: dict[int, ImageRecord] = {}
    with path.open("rb") as handle:
        num_images = read_next_bytes(handle, 8, "Q")[0]
        for _ in range(num_images):
            image_properties = read_next_bytes(handle, 64, "idddddddi")
            image_id = int(image_properties[0])
            name_chars = []
            while True:
                current_char = handle.read(1)
                if current_char == b"":
                    raise EOFError("Unexpected end of file while reading image name.")
                if current_char == b"\x00":
                    break
                name_chars.append(current_char.decode("utf-8"))
            name = "".join(name_chars)
            num_points2d = read_next_bytes(handle, 8, "Q")[0]
            xys = np.zeros((num_points2d, 2), dtype=np.float64)
            for point_idx in range(num_points2d):
                x, y, _point3d_id = read_next_bytes(handle, 24, "ddq")
                xys[point_idx] = (x, y)
            images[image_id] = ImageRecord(image_id=image_id, name=name, xys=xys)
    return images


def read_points3d_binary(path: Path) -> dict[int, Point3DRecord]:
    points: dict[int, Point3DRecord] = {}
    with path.open("rb") as handle:
        num_points = read_next_bytes(handle, 8, "Q")[0]
        for _ in range(num_points):
            point_properties = read_next_bytes(handle, 43, "QdddBBBd")
            point3d_id = int(point_properties[0])
            xyz = np.array(point_properties[1:4], dtype=np.float64)
            track_length = read_next_bytes(handle, 8, "Q")[0]
            track_data = read_next_bytes(handle, 8 * track_length, "ii" * track_length)
            track = [
                (int(track_data[2 * idx]), int(track_data[2 * idx + 1]))
                for idx in range(track_length)
            ]
            points[point3d_id] = Point3DRecord(point3d_id=point3d_id, xyz=xyz, track=track)
    return points


def iter_sparse_models(sparse_root: Path) -> list[Path]:
    return sorted(
        [path for path in sparse_root.iterdir() if path.is_dir() and path.name.isdigit()],
        key=lambda path: int(path.name),
    )


def count_model_images(images_bin_path: Path) -> int:
    return read_num_records(images_bin_path)


def count_model_points(points3d_bin_path: Path) -> int:
    return read_num_records(points3d_bin_path)


def select_sparse_model(sparse_root: Path, explicit_model_id: int | None) -> Path:
    if explicit_model_id is not None:
        model_dir = sparse_root / str(explicit_model_id)
        if not model_dir.exists():
            raise FileNotFoundError(f"Requested sparse model does not exist: {model_dir}")
        return model_dir

    candidates = iter_sparse_models(sparse_root)
    if not candidates:
        raise FileNotFoundError(f"No sparse COLMAP models found in {sparse_root}")

    scored_candidates = []
    for candidate in candidates:
        images_bin = candidate / "images.bin"
        points3d_bin = candidate / "points3D.bin"
        if not images_bin.exists() or not points3d_bin.exists():
            continue
        scored_candidates.append(
            (
                count_model_images(images_bin),
                count_model_points(points3d_bin),
                candidate,
            )
        )
    if not scored_candidates:
        raise FileNotFoundError(f"No usable sparse COLMAP models found in {sparse_root}")
    scored_candidates.sort(key=lambda item: (item[0], item[1], -int(item[2].name)), reverse=True)
    return scored_candidates[0][2]


def resolve_mask_path(masks_dir: Path, image_name: str) -> Path:
    preferred = masks_dir / f"{image_name}.png"
    if preferred.exists():
        return preferred
    fallback = masks_dir / Path(image_name).name
    if fallback.exists():
        return fallback
    raise FileNotFoundError(f"Mask not found for image {image_name!r} in {masks_dir}")


def load_mask(mask_path: Path, erode_pixels: int) -> np.ndarray:
    mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        raise RuntimeError(f"Could not read mask image: {mask_path}")
    mask_binary = mask > 0
    if erode_pixels > 0:
        kernel_size = 2 * erode_pixels + 1
        kernel = np.ones((kernel_size, kernel_size), dtype=np.uint8)
        mask_binary = cv2.erode(mask_binary.astype(np.uint8), kernel, iterations=1) > 0
    return mask_binary


def format_vector(values: np.ndarray) -> str:
    return "(" + ",".join(f"{value:.6f}" for value in values.tolist()) + ")"


def main() -> int:
    args = parse_args()
    if args.min_observations < 1:
        raise ValueError("min-observations must be greater than or equal to 1.")
    if not 0.0 <= args.min_foreground_ratio <= 1.0:
        raise ValueError("min-foreground-ratio must be between 0.0 and 1.0.")
    if not 0.0 <= args.lower_percentile < args.upper_percentile <= 100.0:
        raise ValueError("lower-percentile must be smaller than upper-percentile and both must be in [0, 100].")
    if args.padding_scale < 0.0:
        raise ValueError("padding-scale must be non-negative.")
    if args.min_padding < 0.0:
        raise ValueError("min-padding must be non-negative.")
    if args.erode_pixels < 0:
        raise ValueError("erode-pixels must be non-negative.")

    data_root = get_data_root()
    scene_dir = resolve_path_under_root(data_root, args.scene_dir, "scene-dir")
    masks_dir = resolve_path_under_root(
        data_root,
        args.masks_dir or f"{args.scene_dir}/colmap/masks",
        "masks-dir",
    )
    sparse_root = scene_dir / "colmap" / "sparse"
    output_json_path = resolve_path_under_root(
        data_root,
        args.output_json or f"{args.scene_dir}/sugar_bbox_estimate.json",
        "output-json",
    )

    if not masks_dir.exists():
        raise FileNotFoundError(f"Masks directory does not exist: {masks_dir}")
    if not sparse_root.exists():
        raise FileNotFoundError(f"Sparse directory does not exist: {sparse_root}")

    sparse_model_dir = select_sparse_model(sparse_root, args.sparse_model)
    images = read_images_binary(sparse_model_dir / "images.bin")
    points3d = read_points3d_binary(sparse_model_dir / "points3D.bin")

    mask_cache: dict[str, np.ndarray] = {}

    def get_mask_for_image(image_name: str) -> np.ndarray:
        cached = mask_cache.get(image_name)
        if cached is not None:
            return cached
        mask_path = resolve_mask_path(masks_dir, image_name)
        mask = load_mask(mask_path, args.erode_pixels)
        mask_cache[image_name] = mask
        return mask

    selected_xyzs = []
    valid_points = 0
    ratio_values = []

    for point in points3d.values():
        valid_observations = 0
        foreground_observations = 0

        for image_id, point2d_idx in point.track:
            image = images.get(image_id)
            if image is None or point2d_idx < 0 or point2d_idx >= len(image.xys):
                continue

            x, y = image.xys[point2d_idx]
            mask = get_mask_for_image(image.name)
            px = int(round(float(x)))
            py = int(round(float(y)))
            if px < 0 or py < 0 or py >= mask.shape[0] or px >= mask.shape[1]:
                continue

            valid_observations += 1
            if mask[py, px]:
                foreground_observations += 1

        if valid_observations < args.min_observations:
            continue

        valid_points += 1
        foreground_ratio = foreground_observations / valid_observations
        ratio_values.append(foreground_ratio)
        if foreground_ratio >= args.min_foreground_ratio:
            selected_xyzs.append(point.xyz)

    if not selected_xyzs:
        raise RuntimeError(
            "No sparse 3D points passed the mask-based selection. "
            "Try lowering --min-foreground-ratio, reducing --min-observations, or checking the masks."
        )

    selected_xyzs_array = np.vstack(selected_xyzs)
    lower = np.percentile(selected_xyzs_array, args.lower_percentile, axis=0)
    upper = np.percentile(selected_xyzs_array, args.upper_percentile, axis=0)
    extent = upper - lower
    max_extent = float(np.max(extent))
    padding = np.maximum(extent * args.padding_scale, np.full(3, max(args.min_padding, max_extent * 0.0)))
    bboxmin = lower - padding
    bboxmax = upper + padding
    center = (bboxmin + bboxmax) / 2.0
    final_extent = bboxmax - bboxmin

    output_payload = {
        "scene_dir": str(scene_dir),
        "sparse_model_dir": str(sparse_model_dir),
        "masks_dir": str(masks_dir),
        "selection": {
            "min_observations": args.min_observations,
            "min_foreground_ratio": args.min_foreground_ratio,
            "lower_percentile": args.lower_percentile,
            "upper_percentile": args.upper_percentile,
            "padding_scale": args.padding_scale,
            "min_padding": args.min_padding,
            "erode_pixels": args.erode_pixels,
        },
        "stats": {
            "registered_images": len(images),
            "total_sparse_points": len(points3d),
            "points_with_enough_observations": valid_points,
            "selected_sparse_points": int(len(selected_xyzs)),
            "foreground_ratio_mean": float(np.mean(ratio_values)) if ratio_values else 0.0,
            "foreground_ratio_median": float(np.median(ratio_values)) if ratio_values else 0.0,
        },
        "bboxmin": bboxmin.tolist(),
        "bboxmax": bboxmax.tolist(),
        "center": center.tolist(),
        "extent": final_extent.tolist(),
        "sugar_args": {
            "bboxmin": format_vector(bboxmin),
            "bboxmax": format_vector(bboxmax),
        },
    }

    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    with output_json_path.open("w", encoding="utf-8") as handle:
        json.dump(output_payload, handle, indent=2)
        handle.write("\n")

    print(f"Sparse model: {sparse_model_dir}")
    print(f"Masks directory: {masks_dir}")
    print(
        "Selected sparse points: "
        f"{len(selected_xyzs)}/{len(points3d)} "
        f"(valid tracks: {valid_points}, registered images: {len(images)})"
    )
    print(f"bboxmin: {format_vector(bboxmin)}")
    print(f"bboxmax: {format_vector(bboxmax)}")
    print(f"Saved estimate JSON: {output_json_path}")
    print("Suggested SuGaR command:")
    print(
        f"python scripts/train_sugar.py --scene-dir {args.scene_dir} "
        f"--bboxmin \"{format_vector(bboxmin)}\" --bboxmax \"{format_vector(bboxmax)}\""
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        sys.exit(1)
