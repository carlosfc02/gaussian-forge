from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2

from sam2_common import get_data_root, resolve_path_under_root


WINDOW_NAME = "Select BBox"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Open a video frame, let the user drag a bounding box, and print bbox_xyxy.",
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

    payload = {
        "video_path": args.video,
        "frame_index": args.frame_index,
        "frame_size": {"width": width, "height": height},
        "frame_count": frame_count,
        "bbox_xyxy": bbox_xyxy,
    }

    print("\nJSON snippet:")
    print(json.dumps({"bbox_xyxy": bbox_xyxy}, ensure_ascii=True))
    print("\nDetailed output:")
    print(json.dumps(payload, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        sys.exit(1)
