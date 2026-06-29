from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from pipeline_manifest import build_command_string
from sam2_common import get_data_root, resolve_path_under_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate a refined SuGaR PLY with full-image and object-masked metrics.",
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
    parser.add_argument("--eval-model-dir", help="Temporary compatible model directory relative to data/. Defaults to sugar_output/eval/<scene>/<ply_stem>.")
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


def prepare_eval_model(sugar_ply: Path, base_model_dir: Path, eval_model_dir: Path) -> Path:
    if not sugar_ply.is_file() or sugar_ply.suffix.lower() != ".ply":
        raise FileNotFoundError(f"SuGaR refined PLY does not exist or is not a .ply: {sugar_ply}")
    if not base_model_dir.is_dir():
        raise FileNotFoundError(f"Base 3DGS model directory does not exist: {base_model_dir}")
    if not (base_model_dir / "cfg_args").is_file():
        raise FileNotFoundError(f"Base 3DGS cfg_args not found: {base_model_dir / 'cfg_args'}")

    point_cloud_dir = eval_model_dir / "point_cloud" / "iteration_0"
    point_cloud_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(sugar_ply, point_cloud_dir / "point_cloud.ply")

    for filename in ("cfg_args", "cameras.json", "input.ply", "exposure.json"):
        source = base_model_dir / filename
        if source.is_file():
            shutil.copyfile(source, eval_model_dir / filename)
    return eval_model_dir


def build_3dgs_metrics_command(args: argparse.Namespace, data_root: Path, scene_dir: Path, source_dir: Path, eval_model_dir: Path, output_dir: Path) -> list[str]:
    command = [
        sys.executable,
        str(Path(__file__).resolve().parent / "evaluate_3dgs_masked_metrics.py"),
        "--scene-dir",
        scene_dir.relative_to(data_root).as_posix(),
        "--source-dir",
        source_dir.relative_to(data_root).as_posix(),
        "--model-dir",
        eval_model_dir.relative_to(data_root).as_posix(),
        "--output-dir",
        output_dir.relative_to(data_root).as_posix(),
        "--iteration",
        "0",
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


def annotate_latest_report(output_dir: Path, sugar_ply: Path, base_model_dir: Path, eval_model_dir: Path) -> None:
    latest_path = output_dir / "latest.json"
    if not latest_path.is_file():
        return
    payload = json.loads(latest_path.read_text(encoding="utf-8"))
    payload["metric_type"] = "masked_sugar"
    payload.setdefault("input_paths", {})
    payload["input_paths"].update(
        {
            "sugar_ply": str(sugar_ply),
            "base_model_dir": str(base_model_dir),
            "eval_model_dir": str(eval_model_dir),
        }
    )
    payload.setdefault("parameters", {})
    payload["parameters"]["sugar_ply"] = str(sugar_ply)
    latest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    timestamped = sorted(path for path in output_dir.glob("*.json") if path.name != "latest.json")
    if timestamped:
        timestamped[-1].write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    args = parse_args()
    if args.crop_padding < 0:
        raise ValueError("crop-padding must be >= 0")

    data_root = get_data_root()
    scene_dir = resolve_path_under_root(data_root, args.scene_dir, "scene-dir")
    scene_name = scene_name_from_scene_dir(args.scene_dir)
    source_dir = resolve_path_under_root(data_root, args.source_dir or f"{Path(args.scene_dir).as_posix()}/gs/source", "source-dir")
    base_model_dir = resolve_path_under_root(data_root, args.base_model_dir or f"{Path(args.scene_dir).as_posix()}/gs/model", "base-model-dir")
    sugar_ply = resolve_path_under_root(data_root, args.sugar_ply, "sugar-ply") if args.sugar_ply else latest_refined_sugar_ply(data_root, scene_name)
    output_dir = resolve_path_under_root(data_root, args.output_dir or f"{Path(args.scene_dir).as_posix()}/metrics/masked_sugar", "output-dir")
    eval_model_dir = resolve_path_under_root(
        data_root,
        args.eval_model_dir or f"sugar_output/eval/{scene_name}/{sugar_ply.stem}",
        "eval-model-dir",
    )

    if not source_dir.is_dir():
        raise FileNotFoundError(f"3DGS source directory does not exist: {source_dir}")
    if not (source_dir / "images").is_dir():
        raise FileNotFoundError(f"3DGS source images directory does not exist: {source_dir / 'images'}")
    if not (source_dir / args.masks_dir).is_dir():
        raise FileNotFoundError(f"3DGS masks directory does not exist: {source_dir / args.masks_dir}")

    prepare_eval_model(sugar_ply, base_model_dir, eval_model_dir)
    command = build_3dgs_metrics_command(args, data_root, scene_dir, source_dir, eval_model_dir, output_dir)
    print("[cmd]", build_command_string(command))
    subprocess.run(command, check=True)
    annotate_latest_report(output_dir, sugar_ply, base_model_dir, eval_model_dir)
    print(f"Masked SuGaR metrics: {output_dir / 'latest.json'}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"[error] Command failed with exit code {exc.returncode}", file=sys.stderr)
        raise SystemExit(exc.returncode)
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        raise SystemExit(1)
