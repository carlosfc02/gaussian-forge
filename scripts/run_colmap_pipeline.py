from __future__ import annotations

import argparse
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

from pipeline_manifest import archive_stage_manifest, build_command_string, utc_now_iso
from sam2_common import get_data_root, resolve_path_under_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run COLMAP on a prepared SAM 2 dataset and produce a 3DGS-ready source dataset.",
    )
    parser.add_argument(
        "--scene-dir",
        required=True,
        help="Scene directory relative to data/, for example 3dgs/wood_star.",
    )
    parser.add_argument(
        "--matcher",
        choices=("sequential", "exhaustive"),
        default="sequential",
        help="COLMAP matcher type. Sequential is recommended for video frames.",
    )
    parser.add_argument(
        "--camera-model",
        default="OPENCV",
        help="Camera model for feature extraction. Defaults to OPENCV.",
    )
    parser.add_argument(
        "--single-camera",
        action="store_true",
        help="Treat all frames as coming from the same camera.",
    )
    parser.add_argument(
        "--sequential-overlap",
        type=int,
        default=20,
        help="Sequential matcher overlap. Defaults to 20.",
    )
    parser.add_argument(
        "--use-gpu",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable COLMAP CUDA SIFT. Enabled by default.",
    )
    parser.add_argument(
        "--use-colmap-masks",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Use SAM 2 masks during COLMAP feature extraction. Disabled by default so COLMAP sees the full RGB frames.",
    )
    parser.add_argument(
        "--sparse-model",
        type=int,
        help="Use a specific COLMAP sparse model directory id instead of auto-selecting the best one.",
    )
    parser.add_argument(
        "--skip-feature-extraction",
        action="store_true",
        help="Reuse an existing COLMAP database instead of recomputing features.",
    )
    parser.add_argument(
        "--skip-matching",
        action="store_true",
        help="Skip feature matching.",
    )
    parser.add_argument(
        "--skip-mapping",
        action="store_true",
        help="Skip sparse mapping.",
    )
    parser.add_argument(
        "--skip-undistort",
        action="store_true",
        help="Skip the final image undistortion step.",
    )
    return parser.parse_args()


def run_command(command: list[str], executed_commands: list[str] | None = None) -> None:
    command_string = build_command_string(command)
    print("[cmd]", command_string)
    if executed_commands is not None:
        executed_commands.append(command_string)
    subprocess.run(command, check=True)


def run_command_capture(command: list[str], executed_commands: list[str] | None = None) -> str:
    command_string = build_command_string(command)
    print("[cmd]", command_string)
    if executed_commands is not None:
        executed_commands.append(command_string)
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    output = "\n".join(part for part in [completed.stdout.strip(), completed.stderr.strip()] if part)
    if output:
        print(output)
    return output


def docker_compose_run(service: str, args: list[str]) -> list[str]:
    return ["docker", "compose", "run", "--rm", service, *args]


def reset_path_in_container(path_in_container: str, executed_commands: list[str] | None = None) -> None:
    cleanup_code = (
        "from pathlib import Path; "
        "import shutil, sys; "
        "path = Path(sys.argv[1]); "
        "shutil.rmtree(path, ignore_errors=True) if path.is_dir() else None; "
        "path.unlink() if path.exists() and path.is_file() else None"
    )
    run_command(docker_compose_run("colmap", ["python3", "-c", cleanup_code, path_in_container]), executed_commands)


def iter_sparse_models(sparse_dir: Path) -> list[Path]:
    return sorted(
        [path for path in sparse_dir.iterdir() if path.is_dir() and path.name.isdigit()],
        key=lambda path: int(path.name),
    )


def extract_metric(output: str, label: str) -> float | None:
    match = re.search(rf"{re.escape(label)}:\s+([0-9]+(?:\.[0-9]+)?)", output)
    if not match:
        return None
    return float(match.group(1))


def analyze_sparse_model(
    scene_dir_in_container: str,
    model_dir: Path,
    executed_commands: list[str] | None = None,
) -> dict[str, float | int | None]:
    model_path_in_container = f"{scene_dir_in_container}/colmap/sparse/{model_dir.name}"
    output = run_command_capture(
        docker_compose_run(
            "colmap",
            ["colmap", "model_analyzer", "--path", model_path_in_container],
        ),
        executed_commands,
    )
    registered_images = int(extract_metric(output, "Registered images") or 0)
    points = int(extract_metric(output, "Points") or 0)
    reprojection_error = extract_metric(output, "Mean reprojection error")
    return {
        "model_id": int(model_dir.name),
        "registered_images": registered_images,
        "points": points,
        "reprojection_error": reprojection_error,
    }


def select_sparse_model(
    sparse_dir: Path,
    scene_dir_in_container: str,
    explicit_model_id: int | None,
    executed_commands: list[str] | None = None,
) -> tuple[Path, list[dict[str, float | int | None]], dict[str, float | int | None]]:
    candidates = iter_sparse_models(sparse_dir)
    if not candidates:
        raise FileNotFoundError(f"No COLMAP sparse models were found under {sparse_dir}")

    if explicit_model_id is not None:
        explicit_path = sparse_dir / str(explicit_model_id)
        if not explicit_path.exists():
            raise FileNotFoundError(f"Requested sparse model does not exist: {explicit_path}")
        analysis = analyze_sparse_model(scene_dir_in_container, explicit_path, executed_commands)
        print(f"Using explicitly requested sparse model: {explicit_path}")
        return explicit_path, [analysis], analysis

    analyses = [analyze_sparse_model(scene_dir_in_container, model_dir, executed_commands) for model_dir in candidates]
    best = max(
        analyses,
        key=lambda item: (
            item["registered_images"],
            item["points"],
            -(float(item["reprojection_error"]) if item["reprojection_error"] is not None else float("inf")),
        ),
    )
    print("Sparse model summary:")
    for item in analyses:
        reprojection_error = (
            f"{float(item['reprojection_error']):.6f}"
            if item["reprojection_error"] is not None
            else "n/a"
        )
        print(
            f"  - model {item['model_id']}: registered_images={item['registered_images']}, "
            f"points={item['points']}, reprojection_error={reprojection_error}"
        )
    print(f"Selected sparse model: {best['model_id']}")
    return sparse_dir / str(best["model_id"]), analyses, best


def normalize_3dgs_sparse_layout(scene_dir_in_container: str, executed_commands: list[str] | None = None) -> None:
    sparse_dir_in_container = f"{scene_dir_in_container}/gs/source/sparse"
    normalize_code = (
        "from pathlib import Path; "
        "import shutil, sys; "
        "sparse = Path(sys.argv[1]); "
        "target = sparse / '0'; "
        "target.mkdir(parents=True, exist_ok=True); "
        "[shutil.move(str(path), str(target / path.name)) for path in sparse.iterdir() if path.is_file()]"
    )
    run_command(
        docker_compose_run(
            "colmap",
            ["python3", "-c", normalize_code, sparse_dir_in_container],
        ),
        executed_commands,
    )


def count_files(path: Path) -> int:
    return sum(1 for item in path.iterdir() if item.is_file()) if path.exists() else 0


def main() -> int:
    started = time.time()
    started_at = utc_now_iso()
    args = parse_args()
    data_root = get_data_root()
    scene_dir = resolve_path_under_root(data_root, args.scene_dir, "scene-dir")
    executed_commands: list[str] = []
    stage_durations: dict[str, float] = {}

    colmap_dir = scene_dir / "colmap"
    colmap_images = colmap_dir / "images"
    colmap_masks = colmap_dir / "masks"
    sparse_dir = colmap_dir / "sparse"
    gs_images = scene_dir / "gs" / "images"
    gs_source = scene_dir / "gs" / "source"
    use_gpu_value = "1" if args.use_gpu else "0"

    if not colmap_images.exists():
        raise FileNotFoundError(f"COLMAP images directory does not exist: {colmap_images}")
    if args.use_colmap_masks and not colmap_masks.exists():
        raise FileNotFoundError(f"COLMAP masks directory does not exist: {colmap_masks}")
    if not gs_images.exists():
        raise FileNotFoundError(f"Masked GS images directory does not exist: {gs_images}")

    total_input_images = count_files(colmap_images)
    total_mask_images = count_files(colmap_masks)
    scene_dir_in_container = f"/data/{scene_dir.relative_to(data_root).as_posix()}"
    colmap_dir_in_container = f"{scene_dir_in_container}/colmap"
    gs_dir_in_container = f"{scene_dir_in_container}/gs"
    database_path_in_container = f"{colmap_dir_in_container}/database.db"
    sparse_dir_in_container = f"{colmap_dir_in_container}/sparse"
    gs_source_in_container = f"{gs_dir_in_container}/source"

    if not args.skip_feature_extraction:
        stage_started = time.time()
        reset_path_in_container(database_path_in_container, executed_commands)
        feature_cmd = [
            "colmap",
            "feature_extractor",
            "--database_path",
            database_path_in_container,
            "--image_path",
            f"{colmap_dir_in_container}/images",
            "--ImageReader.camera_model",
            args.camera_model,
            "--FeatureExtraction.use_gpu",
            use_gpu_value,
        ]
        if args.use_colmap_masks:
            feature_cmd.extend(["--ImageReader.mask_path", f"{colmap_dir_in_container}/masks"])
        if args.single_camera:
            feature_cmd.extend(["--ImageReader.single_camera", "1"])
        run_command(docker_compose_run("colmap", feature_cmd), executed_commands)
        stage_durations["feature_extraction_seconds"] = round(time.time() - stage_started, 3)

    if not args.skip_matching:
        stage_started = time.time()
        if args.matcher == "sequential":
            matcher_cmd = [
                "colmap",
                "sequential_matcher",
                "--database_path",
                database_path_in_container,
                "--FeatureMatching.use_gpu",
                use_gpu_value,
                "--SequentialMatching.overlap",
                str(args.sequential_overlap),
            ]
        else:
            matcher_cmd = [
                "colmap",
                "exhaustive_matcher",
                "--database_path",
                database_path_in_container,
                "--FeatureMatching.use_gpu",
                use_gpu_value,
            ]
        run_command(docker_compose_run("colmap", matcher_cmd), executed_commands)
        stage_durations["matching_seconds"] = round(time.time() - stage_started, 3)

    if not args.skip_mapping:
        stage_started = time.time()
        reset_path_in_container(sparse_dir_in_container, executed_commands)
        run_command(
            docker_compose_run(
                "colmap",
                [
                    "python3",
                    "-c",
                    "from pathlib import Path; import sys; Path(sys.argv[1]).mkdir(parents=True, exist_ok=True)",
                    sparse_dir_in_container,
                ],
            ),
            executed_commands,
        )
        mapper_cmd = [
            "colmap",
            "mapper",
            "--database_path",
            database_path_in_container,
            "--image_path",
            f"{colmap_dir_in_container}/images",
            "--output_path",
            sparse_dir_in_container,
        ]
        run_command(docker_compose_run("colmap", mapper_cmd), executed_commands)
        stage_durations["mapping_seconds"] = round(time.time() - stage_started, 3)

    stage_started = time.time()
    sparse_model, candidate_analyses, selected_model_metrics = select_sparse_model(
        sparse_dir,
        scene_dir_in_container,
        args.sparse_model,
        executed_commands,
    )
    stage_durations["model_selection_seconds"] = round(time.time() - stage_started, 3)

    if not args.skip_undistort:
        stage_started = time.time()
        reset_path_in_container(gs_source_in_container, executed_commands)
        undistort_cmd = [
            "colmap",
            "image_undistorter",
            "--image_path",
            f"{gs_dir_in_container}/images",
            "--input_path",
            f"{colmap_dir_in_container}/sparse/{sparse_model.name}",
            "--output_path",
            gs_source_in_container,
            "--output_type",
            "COLMAP",
        ]
        run_command(docker_compose_run("colmap", undistort_cmd), executed_commands)
        normalize_3dgs_sparse_layout(scene_dir_in_container, executed_commands)
        stage_durations["undistort_seconds"] = round(time.time() - stage_started, 3)

    registration_ratio = (
        float(selected_model_metrics["registered_images"]) / total_input_images if total_input_images else 0.0
    )
    finished_at = utc_now_iso()
    duration_seconds = time.time() - started
    manifest = {
        "status": "success",
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": round(duration_seconds, 3),
        "commands": executed_commands,
        "scene_dir": str(scene_dir),
        "input_paths": {
            "colmap_images": str(colmap_images),
            "colmap_masks": str(colmap_masks) if colmap_masks.exists() else None,
            "gs_images": str(gs_images),
        },
        "output_paths": {
            "database_path": str(colmap_dir / "database.db"),
            "sparse_dir": str(sparse_dir),
            "gs_source": str(gs_source),
            "selected_sparse_model": str(sparse_model),
        },
        "parameters": {
            "matcher": args.matcher,
            "camera_model": args.camera_model,
            "single_camera": args.single_camera,
            "sequential_overlap": args.sequential_overlap,
            "use_gpu": args.use_gpu,
            "use_colmap_masks": args.use_colmap_masks,
            "sparse_model": args.sparse_model,
            "skip_feature_extraction": args.skip_feature_extraction,
            "skip_matching": args.skip_matching,
            "skip_mapping": args.skip_mapping,
            "skip_undistort": args.skip_undistort,
        },
        "metrics": {
            "total_input_images": total_input_images,
            "total_mask_images": total_mask_images,
            "registered_images": int(selected_model_metrics["registered_images"]),
            "registration_ratio": registration_ratio,
            "selected_sparse_model_id": int(selected_model_metrics["model_id"]),
            "sparse_point_count": int(selected_model_metrics["points"]),
            "mean_reprojection_error": (
                float(selected_model_metrics["reprojection_error"])
                if selected_model_metrics["reprojection_error"] is not None
                else None
            ),
        },
        "candidate_sparse_models": candidate_analyses,
        "stage_durations": stage_durations,
    }
    metrics_manifest_path = archive_stage_manifest(scene_dir, "colmap", manifest)

    print("COLMAP camera estimation input: original RGB frames")
    print(f"COLMAP masks enabled: {args.use_colmap_masks}")
    print(f"COLMAP GPU enabled: {args.use_gpu}")
    print(f"COLMAP sparse model: {sparse_model}")
    print(f"3DGS source dataset: {gs_source}")
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




