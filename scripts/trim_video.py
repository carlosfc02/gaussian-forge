from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

from sam2_common import get_data_root, resolve_path_under_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a trimmed copy of a video under data/ without modifying the original file.",
    )
    parser.add_argument(
        "--input-video",
        required=True,
        help="Input video path relative to data/, for example videos/mario.mp4.",
    )
    parser.add_argument(
        "--output-video",
        required=True,
        help="Output video path relative to data/, for example videos/mario_trim.mp4.",
    )
    parser.add_argument(
        "--keep-seconds",
        type=float,
        required=True,
        help="Duration to keep from the start of the input video.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.keep_seconds <= 0:
        raise ValueError("keep-seconds must be greater than 0.")

    data_root = get_data_root()
    input_video = resolve_path_under_root(data_root, args.input_video, "input-video")
    output_video = resolve_path_under_root(data_root, args.output_video, "output-video")

    if not input_video.exists():
        raise FileNotFoundError(f"Input video does not exist: {input_video}")
    if input_video == output_video:
        raise ValueError("output-video must be different from input-video.")

    capture = cv2.VideoCapture(str(input_video))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open input video: {input_video}")

    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        if fps <= 0.0:
            raise RuntimeError(f"Could not determine FPS for input video: {input_video}")

        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        if width <= 0 or height <= 0:
            raise RuntimeError(f"Could not determine frame size for input video: {input_video}")

        output_video.parent.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(
            str(output_video),
            cv2.VideoWriter_fourcc(*"mp4v"),
            fps,
            (width, height),
        )
        if not writer.isOpened():
            raise RuntimeError(f"Could not open output video for writing: {output_video}")

        try:
            max_frames = int(args.keep_seconds * fps)
            written_frames = 0

            while written_frames < max_frames:
                ok, frame = capture.read()
                if not ok or frame is None:
                    break
                writer.write(frame)
                written_frames += 1
        finally:
            writer.release()
    finally:
        capture.release()

    print(f"Trimmed video: {output_video}")
    print(f"Written frames: {written_frames}")
    print(f"FPS: {fps:.3f}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        sys.exit(1)
