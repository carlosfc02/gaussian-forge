from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import urllib.request
from pathlib import Path

from sam2_common import CHECKPOINT_SPECS, get_checkpoint_root, resolve_checkpoint_spec


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download SAM 2.1 checkpoints into the mounted model volume.",
    )
    parser.add_argument(
        "--checkpoint",
        default="sam2.1_hiera_small",
        help="Checkpoint name to download or 'all'.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(get_checkpoint_root()),
        help="Directory where checkpoints will be stored.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Redownload files even if they already exist.",
    )
    return parser.parse_args()


def download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(delete=False, dir=destination.parent, suffix=".part") as tmp_handle:
        temp_path = Path(tmp_handle.name)

    try:
        with urllib.request.urlopen(url) as response, temp_path.open("wb") as output_handle:
            shutil.copyfileobj(response, output_handle)
        temp_path.replace(destination)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    names = (
        sorted(CHECKPOINT_SPECS)
        if args.checkpoint == "all"
        else [resolve_checkpoint_spec(args.checkpoint).name]
    )

    for checkpoint_name in names:
        spec = CHECKPOINT_SPECS[checkpoint_name]
        destination = output_dir / spec.filename
        if destination.exists() and not args.force:
            print(f"[skip] {spec.filename} already exists at {destination}")
            continue

        print(f"[download] {checkpoint_name} -> {destination}")
        download_file(spec.url, destination)
        print(f"[ok] {destination}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
