from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2

from sam2_common import DEFAULT_CHECKPOINT, get_data_root, resolve_path_under_root


WINDOW_NAME = "Select BBox"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Open a video frame, let the user drag a bounding box, and optionally create a segmentation job.",
    )
    parser.add_argument(
        "--video",
        required=True,
        help="Video path relative to data/ (for example videos/example.mp4).",
    )
    parser.add_argument(
        "--frame-index",
        type=int,
        default=0,
        help="Frame index to open. Defaults to 0.",
    )
    parser.add_argument(
        "--save-preview",
        help="Optional output path relative to data/ for the selected frame with the drawn bbox.",
    )
    parser.add_argument(
        "--job",
        help="Optional output path for the generated segmentation job JSON. Defaults to jobs/segmentation/<video_stem>_job.json.",
    )
    parser.add_argument(
        "--mask-output-dir",
        help="Optional output_dir value written into the generated job. Defaults to masks/<video_stem>.",
    )
    parser.add_argument(
        "--object-id",
        type=int,
        default=1,
        help="Object id written into the generated job. Defaults to 1.",
    )
    parser.add_argument(
        "--checkpoint",
        default=DEFAULT_CHECKPOINT,
        help=f"Checkpoint name written into the generated job. Defaults to {DEFAULT_CHECKPOINT}.",
    )
    return parser.parse_args()


def load_frame(video_path: Path, frame_index: int) -> tuple[cv2.typing.MatLike, int, int, int]:
    if frame_index < 0:
        raise ValueError("frame-index must be greater than or equal to 0.")

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f"Could not open video file: {video_path}")

    try:
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if frame_count > 0 and frame_index >= frame_count:
            raise ValueError(
                f"frame-index {frame_index} is outside the video range [0, {frame_count - 1}]."
            )

        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = capture.read()
        if not ok or frame is None:
            raise ValueError(f"Could not read frame {frame_index} from: {video_path}")

        height, width = frame.shape[:2]
        return frame, width, height, frame_count
    finally:
        capture.release()


def select_bbox(frame) -> list[int]:
    print("Draw a box with the mouse and press ENTER or SPACE to confirm.")
    print("Press C to cancel and close the window.")

    x, y, w, h = cv2.selectROI(WINDOW_NAME, frame, showCrosshair=True, fromCenter=False)
    cv2.destroyAllWindows()

    if w <= 0 or h <= 0:
        raise RuntimeError("No bbox was selected.")

    return [int(x), int(y), int(x + w), int(y + h)]


def save_preview(frame, bbox_xyxy: list[int], preview_path: Path) -> None:
    x1, y1, x2, y2 = bbox_xyxy
    annotated = frame.copy()
    cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(preview_path), annotated):
        raise RuntimeError(f"Could not save preview image to: {preview_path}")


def get_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_job_path(job_arg: str | None, video_path_arg: str) -> Path:
    repo_root = get_repo_root()
    video_stem = Path(video_path_arg).stem
    default_path = repo_root / "jobs" / "segmentation" / f"{video_stem}_job.json"
    if job_arg is None:
        return default_path

    candidate = Path(job_arg)
    if candidate.is_absolute():
        return candidate.resolve()
    return (repo_root / candidate).resolve()


def build_job_payload(
    *,
    video_path_arg: str,
    mask_output_dir_arg: str | None,
    object_id: int,
    bbox_xyxy: list[int],
    checkpoint: str,
) -> dict:
    video_stem = Path(video_path_arg).stem
    return {
        "video_path": Path(video_path_arg).as_posix(),
        "output_dir": Path(mask_output_dir_arg or f"masks/{video_stem}").as_posix(),
        "object_id": int(object_id),
        "bbox_xyxy": bbox_xyxy,
        "checkpoint": checkpoint,
    }


def write_job(job_path: Path, job_payload: dict) -> None:
    job_path.parent.mkdir(parents=True, exist_ok=True)
    with job_path.open("w", encoding="utf-8") as handle:
        json.dump(job_payload, handle, indent=2, ensure_ascii=True)
        handle.write("\n")


def main() -> int:
    args = parse_args()
    data_root = get_data_root()
    video_path = resolve_path_under_root(data_root, args.video, "video")
    if not video_path.exists():
        raise FileNotFoundError(f"Video file does not exist: {video_path}")

    preview_path = None
    if args.save_preview:
        preview_path = resolve_path_under_root(data_root, args.save_preview, "save-preview")

    frame, width, height, frame_count = load_frame(video_path, args.frame_index)
    bbox_xyxy = select_bbox(frame)

    if preview_path is not None:
        save_preview(frame, bbox_xyxy, preview_path)
        print(f"Saved preview to: {preview_path}")

    if args.object_id < 1:
        raise ValueError("object-id must be greater than or equal to 1.")

    job_path = resolve_job_path(args.job, args.video)
    job_payload = build_job_payload(
        video_path_arg=args.video,
        mask_output_dir_arg=args.mask_output_dir,
        object_id=args.object_id,
        bbox_xyxy=bbox_xyxy,
        checkpoint=args.checkpoint,
    )
    write_job(job_path, job_payload)
    print(f"Saved segmentation job to: {job_path}")

    payload = {
        "video_path": args.video,
        "frame_index": args.frame_index,
        "frame_size": {"width": width, "height": height},
        "frame_count": frame_count,
        "bbox_xyxy": bbox_xyxy,
        "job_path": str(job_path),
        "job": job_payload,
    }

    print("\nJSON snippet:")
    print(json.dumps({"bbox_xyxy": bbox_xyxy}, ensure_ascii=True))
    print("\nGenerated job:")
    print(json.dumps(job_payload, indent=2, ensure_ascii=True))
    print("\nDetailed output:")
    print(json.dumps(payload, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        sys.exit(1)
