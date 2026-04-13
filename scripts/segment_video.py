from __future__ import annotations

import argparse
import json
import os
import sys
import time
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from sam2_common import (
    DEFAULT_CHECKPOINT,
    get_checkpoint_path,
    get_data_root,
    get_model_config_name,
    get_model_config_path,
    resolve_path_under_root,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Segment a single object in a video with SAM 2 using an initial bounding box.",
    )
    parser.add_argument(
        "--job",
        required=True,
        help="Path to a JSON job file, for example /jobs/segmentation/example_job.json.",
    )
    return parser.parse_args()


def load_job(job_path: Path) -> dict:
    with job_path.open("r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)

    required_fields = {"video_path", "output_dir", "object_id", "bbox_xyxy"}
    missing = sorted(required_fields - payload.keys())
    if missing:
        raise ValueError(f"Job file is missing required fields: {', '.join(missing)}")

    payload.setdefault("checkpoint", DEFAULT_CHECKPOINT)
    return payload


def validate_bbox(bbox_xyxy: list[float], width: int, height: int) -> list[float]:
    if not isinstance(bbox_xyxy, list) or len(bbox_xyxy) != 4:
        raise ValueError("bbox_xyxy must be a list of four numeric values [x1, y1, x2, y2].")

    try:
        x1, y1, x2, y2 = [float(value) for value in bbox_xyxy]
    except (TypeError, ValueError) as exc:
        raise ValueError("bbox_xyxy must contain numeric values.") from exc

    if x1 >= x2 or y1 >= y2:
        raise ValueError("bbox_xyxy must satisfy x1 < x2 and y1 < y2.")
    if x1 < 0 or y1 < 0 or x2 > width or y2 > height:
        raise ValueError(
            f"bbox_xyxy {bbox_xyxy} is outside the first frame dimensions ({width}x{height})."
        )

    return [x1, y1, x2, y2]


def inspect_video(video_path: Path) -> dict[str, float | int]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f"Could not open video file: {video_path}")

    try:
        ok, frame = capture.read()
        if not ok or frame is None:
            raise ValueError(f"Could not read the first frame from: {video_path}")

        height, width = frame.shape[:2]
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    finally:
        capture.release()

    return {
        "width": width,
        "height": height,
        "fps": fps,
        "frame_count": frame_count,
    }


def build_manifest(
    *,
    job_payload: dict,
    video_info: dict,
    checkpoint_path: Path,
    config_name: str,
    masks_written: int,
    device: str,
    started_at: str,
    finished_at: str,
    duration_seconds: float,
    status: str,
    error: str | None = None,
) -> dict:
    manifest = {
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": round(duration_seconds, 3),
        "video_path": job_payload["video_path"],
        "output_dir": job_payload["output_dir"],
        "object_id": int(job_payload["object_id"]),
        "prompt": {
            "frame_idx": 0,
            "bbox_xyxy": job_payload["bbox_xyxy"],
        },
        "checkpoint": job_payload["checkpoint"],
        "checkpoint_file": str(checkpoint_path),
        "model_config": config_name,
        "device": device,
        "video_info": video_info,
        "masks_written": masks_written,
    }
    if error is not None:
        manifest["error"] = error
    return manifest


def write_manifest(output_dir: Path, manifest: dict) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
        handle.write(os.linesep)


def select_mask_for_object(object_ids, masks, object_id: int) -> np.ndarray:
    for candidate_id, candidate_mask in zip(object_ids, masks):
        if int(candidate_id) != int(object_id):
            continue
        mask_array = np.asarray(candidate_mask.detach().float().cpu().numpy())
        if mask_array.ndim == 3:
            mask_array = np.squeeze(mask_array, axis=0)
        return (mask_array > 0.0).astype(np.uint8) * 255
    raise RuntimeError(f"SAM 2 did not return a mask for object_id={object_id}.")


def save_mask(mask: np.ndarray, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(mask, mode="L").save(destination)


def main() -> int:
    args = parse_args()
    job_path = Path(args.job).resolve()
    if not job_path.exists():
        raise FileNotFoundError(f"Job file does not exist: {job_path}")

    job_payload = load_job(job_path)
    data_root = get_data_root()
    video_path = resolve_path_under_root(data_root, job_payload["video_path"], "video_path")
    output_dir = resolve_path_under_root(data_root, job_payload["output_dir"], "output_dir")

    if not video_path.exists():
        raise FileNotFoundError(f"Video file does not exist: {video_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    video_info = inspect_video(video_path)
    bbox_xyxy = validate_bbox(job_payload["bbox_xyxy"], video_info["width"], video_info["height"])
    checkpoint_name = job_payload["checkpoint"]
    checkpoint_path = get_checkpoint_path(checkpoint_name)
    config_name = get_model_config_name(checkpoint_name)
    config_path = get_model_config_path(checkpoint_name)

    if not checkpoint_path.exists():
        raise FileNotFoundError(
            f"Checkpoint not found: {checkpoint_path}. Download it first with bootstrap_checkpoints.py."
        )
    if not config_path.exists():
        raise FileNotFoundError(f"Model config not found inside the image: {config_path}")

    started = time.time()
    started_at = datetime.now(timezone.utc).isoformat()
    masks_written = 0
    saved_frames: set[int] = set()

    import torch
    from sam2.build_sam import build_sam2_video_predictor

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type != "cuda":
        raise RuntimeError("CUDA is required for this container, but no GPU was detected inside Docker.")

    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True

    try:
        predictor = build_sam2_video_predictor(
            config_name,
            str(checkpoint_path),
            device=device,
        )

        autocast_context = (
            torch.autocast(device_type="cuda", dtype=torch.bfloat16)
            if device.type == "cuda"
            else nullcontext()
        )

        with torch.inference_mode(), autocast_context:
            inference_state = predictor.init_state(video_path=str(video_path))
            prompt_frame_idx, prompt_object_ids, prompt_masks = predictor.add_new_points_or_box(
                inference_state=inference_state,
                frame_idx=0,
                obj_id=int(job_payload["object_id"]),
                box=np.asarray(bbox_xyxy, dtype=np.float32),
            )

            prompt_mask = select_mask_for_object(
                prompt_object_ids,
                prompt_masks,
                int(job_payload["object_id"]),
            )
            save_mask(prompt_mask, output_dir / f"{int(prompt_frame_idx):06d}.png")
            saved_frames.add(int(prompt_frame_idx))
            masks_written += 1

            for frame_idx, object_ids, mask_logits in predictor.propagate_in_video(inference_state):
                mask = select_mask_for_object(object_ids, mask_logits, int(job_payload["object_id"]))
                save_mask(mask, output_dir / f"{int(frame_idx):06d}.png")
                if int(frame_idx) not in saved_frames:
                    masks_written += 1
                    saved_frames.add(int(frame_idx))

        if masks_written == 0:
            raise RuntimeError("SAM 2 finished without producing any masks.")

        finished_at = datetime.now(timezone.utc).isoformat()
        duration_seconds = time.time() - started
        manifest = build_manifest(
            job_payload={**job_payload, "bbox_xyxy": bbox_xyxy},
            video_info=video_info,
            checkpoint_path=checkpoint_path,
            config_name=config_name,
            masks_written=masks_written,
            device=str(device),
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=duration_seconds,
            status="success",
        )
        write_manifest(output_dir, manifest)
    except Exception as exc:
        finished_at = datetime.now(timezone.utc).isoformat()
        duration_seconds = time.time() - started
        try:
            manifest = build_manifest(
                job_payload={**job_payload, "bbox_xyxy": bbox_xyxy},
                video_info=video_info,
                checkpoint_path=checkpoint_path,
                config_name=config_name,
                masks_written=masks_written,
                device=str(device),
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=duration_seconds,
                status="failed",
                error=str(exc),
            )
            write_manifest(output_dir, manifest)
        except Exception:
            pass
        raise

    print(f"Wrote {masks_written} masks to {output_dir}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        sys.exit(1)
