from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np

from sam2_common import get_data_root, resolve_path_under_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare a COLMAP/3DGS-ready dataset from a video and SAM 2 masks.",
    )
    parser.add_argument(
        "--job",
        required=True,
        help="Path to a segmentation job JSON file.",
    )
    parser.add_argument(
        "--output-dir",
        help="Output path relative to data/. Defaults to 3dgs/<scene_name>.",
    )
    parser.add_argument(
        "--scene-name",
        help="Optional scene name. Defaults to the SAM 2 mask folder name.",
    )
    parser.add_argument(
        "--frame-step",
        type=int,
        default=1,
        help="Keep one frame every N masked frames. Defaults to 1.",
    )
    parser.add_argument(
        "--background",
        choices=("black", "white"),
        default="black",
        help="Background color for the masked images used by 3DGS. Defaults to black.",
    )
    return parser.parse_args()


def load_job(job_path: Path) -> dict:
    with job_path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def list_mask_frames(mask_dir: Path) -> list[tuple[int, Path]]:
    masks = []
    for path in sorted(mask_dir.glob("*.png")):
        try:
            frame_idx = int(path.stem)
        except ValueError:
            continue
        masks.append((frame_idx, path))
    if not masks:
        raise FileNotFoundError(f"No PNG masks found in: {mask_dir}")
    return masks


def make_background(frame: np.ndarray, mask_binary: np.ndarray, background: str) -> np.ndarray:
    masked = frame.copy()
    background_value = 0 if background == "black" else 255
    masked[mask_binary == 0] = background_value
    return masked


def save_image(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), image):
        raise RuntimeError(f"Could not write image: {path}")


def reset_output_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def main() -> int:
    args = parse_args()
    if args.frame_step < 1:
        raise ValueError("frame-step must be greater than or equal to 1.")

    data_root = get_data_root()
    job_path = Path(args.job).resolve()
    if not job_path.exists():
        raise FileNotFoundError(f"Job file does not exist: {job_path}")

    job_payload = load_job(job_path)
    if "video_path" not in job_payload or "output_dir" not in job_payload:
        raise ValueError("Job file must include at least video_path and output_dir.")

    video_path = resolve_path_under_root(data_root, job_payload["video_path"], "video_path")
    mask_dir = resolve_path_under_root(data_root, job_payload["output_dir"], "output_dir")

    if not video_path.exists():
        raise FileNotFoundError(f"Video file does not exist: {video_path}")
    if not mask_dir.exists():
        raise FileNotFoundError(f"Mask directory does not exist: {mask_dir}")

    scene_name = args.scene_name or mask_dir.name
    output_dir = resolve_path_under_root(
        data_root,
        args.output_dir or f"3dgs/{scene_name}",
        "output-dir",
    )

    colmap_images_dir = output_dir / "colmap" / "images"
    colmap_masks_dir = output_dir / "colmap" / "masks"
    gs_images_dir = output_dir / "gs" / "images"

    reset_output_dir(colmap_images_dir)
    reset_output_dir(colmap_masks_dir)
    reset_output_dir(gs_images_dir)

    selected_masks = list_mask_frames(mask_dir)[:: args.frame_step]
    selected_by_frame = {frame_idx: mask_path for frame_idx, mask_path in selected_masks}

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f"Could not open video file: {video_path}")

    try:
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)

        saved = 0
        processed_frames = []
        current_frame_idx = 0

        while True:
            ok, frame = capture.read()
            if not ok or frame is None:
                break

            if current_frame_idx not in selected_by_frame:
                current_frame_idx += 1
                continue

            mask_path = selected_by_frame[current_frame_idx]
            mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
            if mask is None:
                raise RuntimeError(f"Could not read mask image: {mask_path}")

            if mask.shape[:2] != frame.shape[:2]:
                raise RuntimeError(
                    f"Mask/frame size mismatch at frame {current_frame_idx}: mask={mask.shape[:2]}, frame={frame.shape[:2]}"
                )

            mask_binary = (mask > 0).astype(np.uint8)
            masked_frame = make_background(frame, mask_binary, args.background)

            image_file_name = f"{current_frame_idx:06d}.png"
            mask_file_name = f"{image_file_name}.png"
            save_image(colmap_images_dir / image_file_name, frame)
            save_image(colmap_masks_dir / mask_file_name, mask_binary * 255)
            save_image(gs_images_dir / image_file_name, masked_frame)

            processed_frames.append(current_frame_idx)
            saved += 1
            current_frame_idx += 1

        if saved != len(selected_masks):
            missing = sorted(set(selected_by_frame) - set(processed_frames))
            raise RuntimeError(f"Video ended before all masks were processed. Missing frames: {missing[:10]}")

    finally:
        capture.release()

    metadata = {
        "scene_name": scene_name,
        "source": {
            "job_path": str(job_path),
            "video_path": job_payload["video_path"],
            "mask_dir": job_payload["output_dir"],
        },
        "output_dir": str(output_dir),
        "background": args.background,
        "frame_step": args.frame_step,
        "video_info": {
            "frame_count": frame_count,
            "fps": fps,
        },
        "prepared_frames": len(selected_masks),
        "prepared_frame_indices": [frame_idx for frame_idx, _ in selected_masks],
        "directories": {
            "colmap_images": str(colmap_images_dir),
            "colmap_masks": str(colmap_masks_dir),
            "gs_images": str(gs_images_dir),
        },
        "colmap_mask_naming": "Each mask is saved as <image_name>.png, as required by COLMAP mask_path.",
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = output_dir / "dataset_manifest.json"
    with metadata_path.open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)
        handle.write("\n")

    print(f"Prepared {len(selected_masks)} frames in {output_dir}")
    print(f"COLMAP images: {colmap_images_dir}")
    print(f"COLMAP masks: {colmap_masks_dir}")
    print(f"3DGS images: {gs_images_dir}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        sys.exit(1)
