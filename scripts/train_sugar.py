from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

from pipeline_manifest import archive_stage_manifest, build_command_string, utc_now_iso
from sam2_common import get_data_root, resolve_path_under_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Launch the official SuGaR pipeline on a prepared COLMAP dataset.",
    )
    parser.add_argument(
        "--scene-dir",
        required=True,
        help="Scene directory relative to data/, for example 3dgs/wood_star.",
    )
    parser.add_argument(
        "--gs-model-dir",
        help="Vanilla 3DGS model directory relative to data/. Defaults to <scene-dir>/gs/model.",
    )
    parser.add_argument(
        "--regularization",
        choices=["dn_consistency", "density", "sdf"],
        default="dn_consistency",
        help="SuGaR regularization type. Defaults to dn_consistency.",
    )
    parser.add_argument(
        "--sugar-output-root",
        default="sugar_output",
        help=(
            "Global SuGaR output root relative to data/. "
            "The launcher creates <root>/<scene>/ and lets SuGaR write its official output/ "
            "layout there. Defaults to sugar_output."
        ),
    )
    parser.add_argument(
        "--sugar-output-name",
        help=(
            "Optional output folder name created under sugar-output-root. "
            "Defaults to the input scene name."
        ),
    )
    parser.add_argument(
        "--from-scratch",
        action="store_true",
        help="Do not reuse an existing 3DGS model. SuGaR will train its own vanilla 3DGS for 7000 iterations.",
    )
    parser.add_argument(
        "--low-poly",
        action="store_true",
        help="Use SuGaR low-poly configuration.",
    )
    parser.add_argument(
        "--high-poly",
        action="store_true",
        help="Use SuGaR high-poly configuration.",
    )
    parser.add_argument(
        "--refinement-time",
        choices=["short", "medium", "long"],
        help="Shortcut for SuGaR refinement duration.",
    )
    parser.add_argument(
        "--surface-level",
        type=float,
        default=0.3,
        help="Surface level for mesh extraction. Defaults to 0.3.",
    )
    parser.add_argument(
        "--n-vertices",
        type=int,
        help="Override the number of vertices in the extracted mesh.",
    )
    parser.add_argument(
        "--gaussians-per-triangle",
        type=int,
        help="Override the number of Gaussians per triangle in the refined stage.",
    )
    parser.add_argument(
        "--refinement-iterations",
        type=int,
        help="Override refined-stage iterations.",
    )
    parser.add_argument(
        "--square-size",
        type=int,
        default=8,
        help="UV texture square size. Defaults to 8.",
    )
    parser.add_argument(
        "--gpu",
        type=int,
        default=0,
        help="GPU index passed to SuGaR. Defaults to 0.",
    )
    parser.add_argument(
        "--bboxmin",
        help="Optional SuGaR foreground bbox min, for example '(0.0,0.0,0.0)'.",
    )
    parser.add_argument(
        "--bboxmax",
        help="Optional SuGaR foreground bbox max, for example '(1.0,1.0,1.0)'.",
    )
    parser.add_argument(
        "--center-bbox",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Center the custom bbox. Defaults to true.",
    )
    parser.add_argument(
        "--eval",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Use SuGaR eval split. Defaults to false.",
    )
    parser.add_argument(
        "--white-background",
        action="store_true",
        help="Train SuGaR with white background.",
    )
    parser.add_argument(
        "--export-obj",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Export textured OBJ mesh. Defaults to true.",
    )
    parser.add_argument(
        "--export-ply",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Export refined PLY. Defaults to true.",
    )
    parser.add_argument(
        "--postprocess-mesh",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Enable SuGaR mesh postprocessing.",
    )
    parser.add_argument(
        "--postprocess-density-threshold",
        type=float,
        default=0.1,
        help="Density threshold for postprocessing. Defaults to 0.1.",
    )
    parser.add_argument(
        "--postprocess-iterations",
        type=int,
        default=5,
        help="Iterations for mesh postprocessing. Defaults to 5.",
    )
    parser.add_argument(
        "--extra-arg",
        action="append",
        default=[],
        help="Extra argument passed through to train_full_pipeline.py. Repeatable.",
    )
    args = parser.parse_args()
    if args.low_poly and args.high_poly:
        parser.error("--low-poly and --high-poly are mutually exclusive.")
    return args


def bool_str(value: bool) -> str:
    return "True" if value else "False"


def shell_quote_bbox(value: str) -> str:
    stripped = value.strip()
    if stripped.startswith('"') and stripped.endswith('"'):
        return stripped
    return f'"{stripped}"'


def run_command(command: list[str]) -> None:
    print("[cmd]", shlex.join(command))
    subprocess.run(command, check=True)


def summarize_directory(path: Path) -> dict[str, int | bool]:
    if not path.exists():
        return {
            "exists": False,
            "file_count": 0,
            "total_size_bytes": 0,
        }

    file_count = 0
    total_size = 0
    for item in path.rglob("*"):
        if not item.is_file():
            continue
        file_count += 1
        total_size += item.stat().st_size

    return {
        "exists": True,
        "file_count": file_count,
        "total_size_bytes": total_size,
    }


def find_first_file_with_suffix(path: Path, suffix: str) -> Path | None:
    if not path.exists():
        return None
    matches = sorted(candidate for candidate in path.rglob(f"*{suffix}") if candidate.is_file())
    return matches[0] if matches else None


def validate_3dgs_checkpoint(model_dir: Path) -> None:
    iteration_7000 = model_dir / "point_cloud" / "iteration_7000" / "point_cloud.ply"
    if not model_dir.exists():
        raise FileNotFoundError(f"3DGS model directory does not exist: {model_dir}")
    if not iteration_7000.exists():
        raise FileNotFoundError(
            "SuGaR expects a vanilla 3DGS checkpoint at iteration 7000. "
            f"Missing: {iteration_7000}"
        )


def sanitize_camera_name(name: str) -> str:
    suffix = Path(name).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg"}:
        return Path(name).stem
    return name


def prepare_sugar_checkpoint_dir(model_dir: Path, scene_dir: Path) -> Path:
    compat_dir = scene_dir / "gs" / "model_sugar_compat"
    compat_dir.mkdir(parents=True, exist_ok=True)

    cameras_path = model_dir / "cameras.json"
    if not cameras_path.exists():
        raise FileNotFoundError(f"3DGS cameras.json does not exist: {cameras_path}")

    cameras = json.loads(cameras_path.read_text(encoding="utf-8"))
    sanitized = []
    changed = False
    for camera in cameras:
        new_camera = dict(camera)
        old_name = str(new_camera.get("img_name", ""))
        new_name = sanitize_camera_name(old_name)
        if new_name != old_name:
            changed = True
        new_camera["img_name"] = new_name
        sanitized.append(new_camera)

    (compat_dir / "cameras.json").write_text(
        json.dumps(sanitized, indent=2),
        encoding="utf-8",
    )

    point_cloud_src = model_dir / "point_cloud" / "iteration_7000" / "point_cloud.ply"
    point_cloud_dst = compat_dir / "point_cloud" / "iteration_7000" / "point_cloud.ply"
    point_cloud_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(point_cloud_src, point_cloud_dst)

    for optional_name in ("cfg_args", "input.ply", "exposure.json"):
        optional_src = model_dir / optional_name
        if optional_src.exists():
            shutil.copy2(optional_src, compat_dir / optional_name)

    if changed:
        print(f"Prepared SuGaR-compatible checkpoint with sanitized camera names: {compat_dir}")
    else:
        print(f"Prepared SuGaR-compatible checkpoint: {compat_dir}")
    return compat_dir


def main() -> int:
    started = time.time()
    started_at = utc_now_iso()
    args = parse_args()
    data_root = get_data_root()
    scene_dir = resolve_path_under_root(data_root, args.scene_dir, "scene-dir")
    scene_name = scene_dir.name
    sugar_output_name = args.sugar_output_name or scene_name
    source_dir = scene_dir / "gs" / "source"

    if not source_dir.exists():
        raise FileNotFoundError(f"SuGaR source dataset does not exist: {source_dir}")
    if not (source_dir / "images").exists():
        raise FileNotFoundError(f"SuGaR source images directory does not exist: {source_dir / 'images'}")
    if not (source_dir / "sparse" / "0").exists():
        raise FileNotFoundError(f"SuGaR sparse model does not exist: {source_dir / 'sparse' / '0'}")

    gs_model_dir: Path | None = None
    sugar_gs_model_dir: Path | None = None
    if not args.from_scratch:
        gs_model_dir = resolve_path_under_root(
            data_root,
            args.gs_model_dir or f"{Path(args.scene_dir).as_posix()}/gs/model",
            "gs-model-dir",
        )
        validate_3dgs_checkpoint(gs_model_dir)
        sugar_gs_model_dir = prepare_sugar_checkpoint_dir(gs_model_dir, scene_dir)

    sugar_output_root = resolve_path_under_root(data_root, args.sugar_output_root, "sugar-output-root")
    sugar_scene_output_dir = sugar_output_root / sugar_output_name
    sugar_scene_output_dir.mkdir(parents=True, exist_ok=True)

    source_dir_in_container = f"/data/{source_dir.relative_to(data_root).as_posix()}"
    sugar_output_root_in_container = f"/data/{sugar_scene_output_dir.relative_to(data_root).as_posix()}"

    command = [
        "docker",
        "compose",
        "run",
        "--rm",
        "-e",
        f"SUGAR_OUTPUT_ROOT={sugar_output_root_in_container}",
        "sugar",
        "conda",
        "run",
        "--no-capture-output",
        "-n",
        "sugar",
        "python",
        "train_full_pipeline.py",
        "-s",
        source_dir_in_container,
        "-r",
        args.regularization,
        "-l",
        str(args.surface_level),
        "--center_bbox",
        bool_str(args.center_bbox),
        "--eval",
        bool_str(args.eval),
        "--gpu",
        str(args.gpu),
        "--white_background",
        bool_str(args.white_background),
        "--export_obj",
        bool_str(args.export_obj),
        "--export_ply",
        bool_str(args.export_ply),
        "--postprocess_mesh",
        bool_str(args.postprocess_mesh),
        "--postprocess_density_threshold",
        str(args.postprocess_density_threshold),
        "--postprocess_iterations",
        str(args.postprocess_iterations),
        "--square_size",
        str(args.square_size),
    ]

    if sugar_gs_model_dir is not None:
        gs_model_dir_in_container = f"/data/{sugar_gs_model_dir.relative_to(data_root).as_posix()}"
        command.extend(["--gs_output_dir", gs_model_dir_in_container])
    if args.low_poly:
        command.extend(["--low_poly", "True"])
    if args.high_poly:
        command.extend(["--high_poly", "True"])
    if args.refinement_time:
        command.extend(["--refinement_time", args.refinement_time])
    if args.n_vertices is not None:
        command.extend(["-v", str(args.n_vertices)])
    if args.gaussians_per_triangle is not None:
        command.extend(["-g", str(args.gaussians_per_triangle)])
    if args.refinement_iterations is not None:
        command.extend(["-f", str(args.refinement_iterations)])
    if args.bboxmin is not None:
        command.extend(["--bboxmin", shell_quote_bbox(args.bboxmin)])
    if args.bboxmax is not None:
        command.extend(["--bboxmax", shell_quote_bbox(args.bboxmax)])
    command.extend(args.extra_arg)

    run_command(command)
    coarse_dir = sugar_scene_output_dir / "coarse" / "source"
    coarse_mesh_dir = sugar_scene_output_dir / "coarse_mesh" / "source"
    refined_dir = sugar_scene_output_dir / "refined" / "source"
    refined_mesh_dir = sugar_scene_output_dir / "refined_mesh" / "source"
    refined_ply_dir = sugar_scene_output_dir / "refined_ply" / "source"
    refined_obj = find_first_file_with_suffix(refined_mesh_dir, ".obj")
    refined_ply = find_first_file_with_suffix(refined_ply_dir, ".ply")
    finished_at = utc_now_iso()
    duration_seconds = time.time() - started
    manifest = {
        "status": "success",
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": round(duration_seconds, 3),
        "command": build_command_string(command),
        "scene_dir": str(scene_dir),
        "input_paths": {
            "source_dir": str(source_dir),
            "gs_model_dir": str(gs_model_dir) if gs_model_dir else None,
            "sugar_compat_dir": str(sugar_gs_model_dir) if sugar_gs_model_dir else None,
        },
        "output_paths": {
            "sugar_output_root": str(sugar_output_root),
            "sugar_scene_output_dir": str(sugar_scene_output_dir),
            "coarse_dir": str(coarse_dir),
            "coarse_mesh_dir": str(coarse_mesh_dir),
            "refined_dir": str(refined_dir),
            "refined_mesh_dir": str(refined_mesh_dir),
            "refined_ply_dir": str(refined_ply_dir),
        },
        "parameters": {
            "regularization": args.regularization,
            "from_scratch": args.from_scratch,
            "sugar_output_name": sugar_output_name,
            "low_poly": args.low_poly,
            "high_poly": args.high_poly,
            "refinement_time": args.refinement_time,
            "surface_level": args.surface_level,
            "n_vertices": args.n_vertices,
            "gaussians_per_triangle": args.gaussians_per_triangle,
            "refinement_iterations": args.refinement_iterations,
            "square_size": args.square_size,
            "gpu": args.gpu,
            "bboxmin": args.bboxmin,
            "bboxmax": args.bboxmax,
            "center_bbox": args.center_bbox,
            "eval": args.eval,
            "white_background": args.white_background,
            "export_obj": args.export_obj,
            "export_ply": args.export_ply,
            "postprocess_mesh": args.postprocess_mesh,
            "postprocess_density_threshold": args.postprocess_density_threshold,
            "postprocess_iterations": args.postprocess_iterations,
            "extra_arg": args.extra_arg,
        },
        "artifacts": {
            "coarse_dir": summarize_directory(coarse_dir),
            "coarse_mesh_dir": summarize_directory(coarse_mesh_dir),
            "refined_dir": summarize_directory(refined_dir),
            "refined_mesh_dir": summarize_directory(refined_mesh_dir),
            "refined_ply_dir": summarize_directory(refined_ply_dir),
            "refined_obj_path": str(refined_obj) if refined_obj else None,
            "refined_obj_size_bytes": refined_obj.stat().st_size if refined_obj and refined_obj.exists() else None,
            "refined_ply_path": str(refined_ply) if refined_ply else None,
            "refined_ply_size_bytes": refined_ply.stat().st_size if refined_ply and refined_ply.exists() else None,
        },
    }
    metrics_manifest_path = archive_stage_manifest(scene_dir, "train_sugar", manifest)

    print(f"SuGaR output root: {sugar_output_root}")
    print(f"SuGaR scene output: {sugar_scene_output_dir}")
    print(f"Coarse outputs: {sugar_scene_output_dir / 'coarse' / 'source'}")
    print(f"Coarse meshes: {sugar_scene_output_dir / 'coarse_mesh' / 'source'}")
    print(f"Refined outputs: {sugar_scene_output_dir / 'refined' / 'source'}")
    print(f"Refined meshes: {sugar_scene_output_dir / 'refined_mesh' / 'source'}")
    print(f"Refined PLY: {sugar_scene_output_dir / 'refined_ply' / 'source'}")
    print(f"Saved metrics manifest: {metrics_manifest_path}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as exc:
        print(f"[error] Command failed with exit code {exc.returncode}", file=sys.stderr)
        sys.exit(exc.returncode)
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        sys.exit(1)
