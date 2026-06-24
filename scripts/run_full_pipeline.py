from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from pipeline_manifest import build_command_string, utc_now_iso, write_json
from pipeline_presets import PRESETS, PipelinePreset
from sam2_common import DEFAULT_CHECKPOINT, get_data_root, resolve_path_under_root


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the full GaussianForge object-centric reconstruction pipeline.",
    )
    parser.add_argument("--video", required=True, help="Input video path relative to data/.")
    parser.add_argument("--scene-name", required=True, help="Scene name used for default output folders.")
    parser.add_argument(
        "--preset",
        choices=sorted(PRESETS),
        default="balanced",
        help="Quality preset. Defaults to balanced.",
    )
    parser.add_argument("--run-name", help="Optional run id used for logs. Model output names stay stable by default.")
    parser.add_argument("--force", action="store_true", help="Allow overwriting stage outputs.")

    parser.add_argument("--mask-loss", action="store_true", help="Train 3DGS with masked RGB loss.")
    parser.add_argument("--metrics", action="store_true", help="Enable 3DGS eval metrics and parse them.")
    parser.add_argument("--white-background", action="store_true", help="Use white background in 3DGS/SuGaR.")

    parser.add_argument("--skip-bbox", action="store_true", help="Do not open bbox selector; reuse --job-path.")
    parser.add_argument("--skip-segmentation", action="store_true", help="Reuse existing masks.")
    parser.add_argument("--skip-prepare", action="store_true", help="Reuse prepared dataset.")
    parser.add_argument("--skip-colmap", action="store_true", help="Reuse existing COLMAP/3DGS source dataset.")
    parser.add_argument("--skip-3dgs", action="store_true", help="Reuse existing 3DGS model.")
    parser.add_argument("--skip-sugar", action="store_true", help="Skip SuGaR training; with --metrics, reuse an existing SuGaR output for metrics.")
    parser.add_argument("--run-sugar", action="store_true", help="Run SuGaR even when the selected preset skips it by default.")
    parser.add_argument(
        "--delegate-docker-to-wsl",
        action="store_true",
        help=(
            "Experimental: when launched from Windows Python over a WSL UNC path, run bbox on Windows "
            "and continue Docker stages through wsl.exe."
        ),
    )

    parser.add_argument("--job-path", help="Segmentation job path. Defaults to jobs/segmentation/<scene-name>_job.json.")
    parser.add_argument("--mask-output-dir", help="Mask output path relative to data/. Defaults to masks/<scene-name>.")
    parser.add_argument("--dataset-dir", help="Dataset path relative to data/. Defaults to 3dgs/<scene-name>.")
    parser.add_argument("--gs-model-dir", help="3DGS model path relative to data/.")
    parser.add_argument("--sugar-output-name", help="SuGaR output folder name.")

    parser.add_argument("--frame-index", type=int, default=0, help="Frame used for bbox selection. Defaults to 0.")
    parser.add_argument("--object-id", type=int, default=1, help="SAM2 object id. Defaults to 1.")
    parser.add_argument("--checkpoint", default=DEFAULT_CHECKPOINT, help=f"SAM2 checkpoint. Defaults to {DEFAULT_CHECKPOINT}.")
    parser.add_argument(
        "--bbox-runner",
        choices=("auto", "host", "windows"),
        default="auto",
        help=(
            "Where to run the interactive bbox selector. auto uses Windows from WSL when available, "
            "otherwise the current Python."
        ),
    )

    parser.add_argument("--frame-step", type=int, help="Override preset frame step.")
    parser.add_argument("--iterations", type=int, help="Override preset 3DGS iterations.")
    parser.add_argument("--sequential-overlap", type=int, help="Override preset COLMAP sequential overlap.")
    parser.add_argument(
        "--matcher",
        choices=("sequential", "exhaustive"),
        default="sequential",
        help="COLMAP matcher. Defaults to sequential.",
    )
    parser.add_argument("--camera-model", default="OPENCV", help="COLMAP camera model. Defaults to OPENCV.")
    parser.add_argument("--single-camera", dest="single_camera", action="store_true", default=True)
    parser.add_argument("--multi-camera", dest="single_camera", action="store_false")
    parser.add_argument("--use-gpu", dest="use_gpu", action="store_true", default=None)
    parser.add_argument("--no-use-gpu", dest="use_gpu", action="store_false")
    parser.add_argument("--use-colmap-masks", dest="use_colmap_masks", action="store_true", default=None)
    parser.add_argument("--no-use-colmap-masks", dest="use_colmap_masks", action="store_false")
    parser.add_argument("--sparse-model", help="COLMAP sparse model directory id to reuse.")
    parser.add_argument("--skip-feature-extraction", action="store_true", help="Reuse an existing COLMAP database.")
    parser.add_argument("--skip-matching", action="store_true", help="Skip COLMAP matching.")
    parser.add_argument("--skip-mapping", action="store_true", help="Skip COLMAP sparse mapping.")
    parser.add_argument("--skip-undistort", action="store_true", help="Skip COLMAP undistortion.")

    parser.add_argument("--resolution", type=int, default=1, help="3DGS resolution argument. Defaults to 1.")
    parser.add_argument("--eval-3dgs", action="store_true", help="Enable the 3DGS eval split without running metrics.")
    parser.add_argument("--masks-dir", help="Mask directory inside the 3DGS source dataset. Defaults to masks.")

    parser.add_argument("--sugar-output-root", default="sugar_output", help="SuGaR output root relative to data/.")
    parser.add_argument("--sugar-regularization", choices=("dn_consistency", "density", "sdf"), default="dn_consistency")
    parser.add_argument("--sugar-refinement-time", choices=("short", "medium", "long"), help="Override preset SuGaR refinement time.")
    parser.add_argument("--sugar-quality-mode", choices=("preset", "low", "high"), default="preset", help="Override preset SuGaR quality mode.")
    parser.add_argument("--surface-level", type=float)
    parser.add_argument("--n-vertices", type=int)
    parser.add_argument("--gaussians-per-triangle", type=int)
    parser.add_argument("--refinement-iterations", type=int)
    parser.add_argument("--square-size", type=int)
    parser.add_argument("--sugar-gpu", type=int)
    parser.add_argument("--bboxmin")
    parser.add_argument("--bboxmax")
    parser.add_argument("--center-bbox", dest="center_bbox", action="store_true", default=None)
    parser.add_argument("--no-center-bbox", dest="center_bbox", action="store_false")
    parser.add_argument("--export-obj", dest="export_obj", action="store_true", default=None)
    parser.add_argument("--no-export-obj", dest="export_obj", action="store_false")
    parser.add_argument("--export-ply", dest="export_ply", action="store_true", default=None)
    parser.add_argument("--no-export-ply", dest="export_ply", action="store_false")
    parser.add_argument("--postprocess-mesh", dest="postprocess_mesh", action="store_true", default=None)
    parser.add_argument("--no-postprocess-mesh", dest="postprocess_mesh", action="store_false")
    parser.add_argument("--postprocess-density-threshold", type=float)
    parser.add_argument("--postprocess-iterations", type=int)
    parser.add_argument("--extra-3dgs-arg", action="append", default=[], help="Extra arg passed to train_3dgs.py. Repeatable.")
    parser.add_argument("--extra-sugar-arg", action="append", default=[], help="Extra arg passed to train_sugar.py. Repeatable.")
    return parser.parse_args()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_run_name() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def resolve_repo_path(path_arg: str | None, default: Path) -> Path:
    if path_arg is None:
        return default.resolve()
    candidate = Path(path_arg)
    if candidate.is_absolute():
        return candidate.resolve()
    return (repo_root() / candidate).resolve()


def relative_to_repo(path: Path) -> str:
    return path.resolve().relative_to(repo_root()).as_posix()


def relative_to_data(path: Path, data_root: Path) -> str:
    return path.resolve().relative_to(data_root.resolve()).as_posix()


def job_path_in_container(job_path: Path) -> str:
    jobs_root = repo_root() / "jobs"
    try:
        relative = job_path.resolve().relative_to(jobs_root.resolve())
    except ValueError as exc:
        raise ValueError("SAM2 Docker can only read job files under the repository jobs/ directory.") from exc
    return f"/jobs/{relative.as_posix()}"


def ensure_can_write_stage(path: Path, stage: str, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"{stage} output already exists: {path}. Use --force or skip the stage.")


def running_windows_python_from_wsl_unc(path: Path) -> bool:
    if os.name != "nt":
        return False
    normalized = str(path).replace("/", "\\").lower()
    return normalized.startswith("\\\\wsl.localhost\\") or normalized.startswith("\\\\wsl$\\")


def running_in_wsl() -> bool:
    if os.name == "nt":
        return False
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        return "microsoft" in Path("/proc/sys/kernel/osrelease").read_text(encoding="utf-8").lower()
    except OSError:
        return False


def linux_path_to_windows_unc(path: Path) -> str:
    try:
        result = subprocess.run(
            ["wslpath", "-w", str(path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        distro = os.environ.get("WSL_DISTRO_NAME", "Ubuntu")
        return f"\\\\wsl.localhost\\{distro}\\" + str(path).lstrip("/").replace("/", "\\")


def powershell_single_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def windows_bbox_available() -> bool:
    return running_in_wsl() and shutil.which("powershell.exe") is not None


def docker_stage_requested(args: argparse.Namespace) -> bool:
    return (
        not args.skip_segmentation
        or not args.skip_colmap
        or not args.skip_3dgs
        or not args.skip_sugar
        or args.metrics
    )


def wsl_unc_to_linux_path(path: Path) -> tuple[str, str] | None:
    normalized = str(path).replace("/", "\\")
    lower = normalized.lower()
    for prefix in ("\\\\wsl.localhost\\", "\\\\wsl$\\"):
        if lower.startswith(prefix):
            remainder = normalized[len(prefix):]
            parts = remainder.split("\\", 1)
            if len(parts) != 2:
                return None
            distro, linux_remainder = parts
            return distro, "/" + linux_remainder.replace("\\", "/")
    return None


def append_optional_arg(command: list[str], flag: str, value: str | None) -> None:
    if value is not None:
        command.extend([flag, value])


def append_optional_bool_arg(command: list[str], value: bool | None, true_flag: str, false_flag: str) -> None:
    if value is None:
        return
    command.append(true_flag if value else false_flag)


def append_passthrough_arg(command: list[str], flag: str, value: str) -> None:
    command.append(f"{flag}={value}")


def build_wsl_continuation_command(args: argparse.Namespace, job_path: Path, run_name: str) -> list[str]:
    command = [
        "python3",
        "scripts/run_full_pipeline.py",
        "--video",
        args.video,
        "--scene-name",
        args.scene_name,
        "--preset",
        args.preset,
        "--run-name",
        run_name,
        "--skip-bbox",
        "--job-path",
        relative_to_repo(job_path),
    ]

    if args.force:
        command.append("--force")
    if args.metrics:
        command.append("--metrics")
    if args.mask_loss:
        command.append("--mask-loss")
    if args.white_background:
        command.append("--white-background")
    if args.skip_segmentation:
        command.append("--skip-segmentation")
    if args.skip_prepare:
        command.append("--skip-prepare")
    if args.skip_colmap:
        command.append("--skip-colmap")
    if args.skip_3dgs:
        command.append("--skip-3dgs")
    if args.skip_sugar:
        command.append("--skip-sugar")
    if args.run_sugar:
        command.append("--run-sugar")

    append_optional_arg(command, "--mask-output-dir", args.mask_output_dir)
    append_optional_arg(command, "--dataset-dir", args.dataset_dir)
    append_optional_arg(command, "--gs-model-dir", args.gs_model_dir)
    append_optional_arg(command, "--sugar-output-name", args.sugar_output_name)
    append_optional_arg(command, "--frame-step", str(args.frame_step) if args.frame_step is not None else None)
    append_optional_arg(command, "--iterations", str(args.iterations) if args.iterations is not None else None)
    append_optional_arg(
        command,
        "--sequential-overlap",
        str(args.sequential_overlap) if args.sequential_overlap is not None else None,
    )
    command.extend(["--matcher", args.matcher])
    command.extend(["--camera-model", args.camera_model])
    if args.single_camera:
        command.append("--single-camera")
    else:
        command.append("--multi-camera")
    append_optional_bool_arg(command, args.use_gpu, "--use-gpu", "--no-use-gpu")
    append_optional_bool_arg(command, args.use_colmap_masks, "--use-colmap-masks", "--no-use-colmap-masks")
    append_optional_arg(command, "--sparse-model", args.sparse_model)
    if args.skip_feature_extraction:
        command.append("--skip-feature-extraction")
    if args.skip_matching:
        command.append("--skip-matching")
    if args.skip_mapping:
        command.append("--skip-mapping")
    if args.skip_undistort:
        command.append("--skip-undistort")

    command.extend(["--resolution", str(args.resolution)])
    if args.eval_3dgs:
        command.append("--eval-3dgs")
    append_optional_arg(command, "--masks-dir", args.masks_dir)

    command.extend(["--sugar-output-root", args.sugar_output_root])
    command.extend(["--sugar-regularization", args.sugar_regularization])
    append_optional_arg(command, "--sugar-refinement-time", args.sugar_refinement_time)
    command.extend(["--sugar-quality-mode", args.sugar_quality_mode])
    append_optional_arg(command, "--surface-level", str(args.surface_level) if args.surface_level is not None else None)
    append_optional_arg(command, "--n-vertices", str(args.n_vertices) if args.n_vertices is not None else None)
    append_optional_arg(command, "--gaussians-per-triangle", str(args.gaussians_per_triangle) if args.gaussians_per_triangle is not None else None)
    append_optional_arg(command, "--refinement-iterations", str(args.refinement_iterations) if args.refinement_iterations is not None else None)
    append_optional_arg(command, "--square-size", str(args.square_size) if args.square_size is not None else None)
    append_optional_arg(command, "--sugar-gpu", str(args.sugar_gpu) if args.sugar_gpu is not None else None)
    append_optional_arg(command, "--bboxmin", args.bboxmin)
    append_optional_arg(command, "--bboxmax", args.bboxmax)
    append_optional_bool_arg(command, args.center_bbox, "--center-bbox", "--no-center-bbox")
    append_optional_bool_arg(command, args.export_obj, "--export-obj", "--no-export-obj")
    append_optional_bool_arg(command, args.export_ply, "--export-ply", "--no-export-ply")
    append_optional_bool_arg(command, args.postprocess_mesh, "--postprocess-mesh", "--no-postprocess-mesh")
    append_optional_arg(command, "--postprocess-density-threshold", str(args.postprocess_density_threshold) if args.postprocess_density_threshold is not None else None)
    append_optional_arg(command, "--postprocess-iterations", str(args.postprocess_iterations) if args.postprocess_iterations is not None else None)

    for extra_arg in args.extra_3dgs_arg:
        command.extend(["--extra-3dgs-arg", extra_arg])
    for extra_arg in args.extra_sugar_arg:
        command.extend(["--extra-sugar-arg", extra_arg])

    return command


def delegate_docker_stages_to_wsl(
    root: Path,
    args: argparse.Namespace,
    job_path: Path,
    run_name: str,
    log_dir: Path,
    manifest: dict,
) -> int | None:
    if not docker_stage_requested(args) or not running_windows_python_from_wsl_unc(root):
        return None
    if not args.delegate_docker_to_wsl:
        continuation = build_wsl_continuation_command(args, job_path, run_name)
        readable = " \\\n".join(shlex.quote(part) if index == 0 else f"  {shlex.quote(part)}" for index, part in enumerate(continuation))
        raise RuntimeError(
            "PowerShell/Windows Python can run the bbox UI, but Docker Desktop is unstable on this machine "
            "when Docker stages are launched through the PowerShell -> WSL bridge. To avoid crashing Docker, "
            "continue from WSL manually with:\n\n"
            f"cd ~/TFG\n{readable}\n\n"
            "If you explicitly want the script to try the bridge anyway, add --delegate-docker-to-wsl."
        )

    unc = wsl_unc_to_linux_path(root)
    if unc is None:
        raise RuntimeError(f"Could not map WSL UNC repository path to a Linux path: {root}")
    distro, linux_root = unc
    continuation = build_wsl_continuation_command(args, job_path, run_name)
    bash_command = f"cd {shlex.quote(linux_root)} && " + " ".join(shlex.quote(part) for part in continuation)
    wsl_command = ["wsl.exe", "-d", distro, "bash", "-lc", bash_command]

    manifest["status"] = "delegated_to_wsl"
    manifest["delegated_to_wsl"] = {
        "distro": distro,
        "linux_root": linux_root,
        "command": build_command_string(wsl_command),
    }
    write_json(log_dir / "full_pipeline_manifest.json", manifest)

    print("[delegate] Continuing Docker-backed stages in WSL.")
    print("[cmd]", build_command_string(wsl_command))
    safe_cwd = str(Path.home()) if os.name == "nt" else str(root)
    return subprocess.call(wsl_command, cwd=safe_cwd)


def require_host_python_module(module_name: str, stage: str, install_hint: str) -> None:
    result = subprocess.run(
        [sys.executable, "-c", f"import {module_name}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"{stage} requires Python module '{module_name}' in the host environment used by "
            f"{sys.executable}. Install it with: {install_hint}. "
            f"If you already have a segmentation job, rerun with --skip-bbox --job-path <job.json>."
        )


def select_bbox_runner(args: argparse.Namespace) -> str:
    if args.bbox_runner == "windows":
        if not windows_bbox_available():
            raise RuntimeError("--bbox-runner windows requires WSL with powershell.exe available.")
        return "windows"
    if args.bbox_runner == "host":
        return "host"
    if windows_bbox_available():
        return "windows"
    return "host"


def build_select_bbox_command(
    args: argparse.Namespace,
    root: Path,
    job_path: Path,
    mask_output_dir: str,
) -> list[str]:
    preview_path = f"frames_videos/{args.scene_name}_bbox_preview.png"
    common_args = [
        "--video",
        args.video,
        "--frame-index",
        str(args.frame_index),
        "--save-preview",
        preview_path,
        "--job",
        relative_to_repo(job_path),
        "--mask-output-dir",
        mask_output_dir,
        "--object-id",
        str(args.object_id),
        "--checkpoint",
        args.checkpoint,
    ]

    runner = select_bbox_runner(args)
    if runner == "host":
        require_host_python_module(
            "cv2",
            "BBox selection",
            f"{sys.executable} -m pip install opencv-python",
        )
        return [sys.executable, str(root / "scripts" / "select_bbox.py"), *common_args]

    repo_unc = linux_path_to_windows_unc(root)
    ps_parts = [
        "$ErrorActionPreference = 'Stop'",
        f"Set-Location -LiteralPath {powershell_single_quote(repo_unc)}",
        "python "
        + " ".join(
            [
                powershell_single_quote(".\\scripts\\select_bbox.py"),
                *(powershell_single_quote(arg) for arg in common_args),
            ]
        ),
    ]
    ps_command = "; ".join(ps_parts)
    return ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_command]


def remove_if_force(path: Path, force: bool) -> None:
    if not force or not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def run_logged(command: list[str], log_path: Path) -> str:
    print("[cmd]", build_command_string(command))
    log_path.parent.mkdir(parents=True, exist_ok=True)

    output_parts: list[str] = []
    with log_path.open("w", encoding="utf-8", errors="replace") as log_handle:
        process = subprocess.Popen(
            command,
            cwd=repo_root(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="", flush=True)
            log_handle.write(line)
            log_handle.flush()
            output_parts.append(line)
        return_code = process.wait()

    if return_code != 0:
        raise subprocess.CalledProcessError(return_code, command)
    return "".join(output_parts)


def run_stage(command: list[str], stage: str, log_dir: Path, manifest: dict) -> str:
    started = time.time()
    started_at = utc_now_iso()
    log_path = log_dir / f"{stage}.log"
    stage_record = {
        "stage": stage,
        "status": "running",
        "started_at": started_at,
        "command": build_command_string(command),
        "log_path": str(log_path),
    }
    manifest["stages"].append(stage_record)

    try:
        output = run_logged(command, log_path)
    except Exception as exc:
        stage_record["status"] = "failed"
        stage_record["finished_at"] = utc_now_iso()
        stage_record["duration_seconds"] = round(time.time() - started, 3)
        stage_record["error"] = str(exc)
        write_json(log_dir / "full_pipeline_manifest.json", manifest)
        raise

    stage_record["status"] = "success"
    stage_record["finished_at"] = utc_now_iso()
    stage_record["duration_seconds"] = round(time.time() - started, 3)
    write_json(log_dir / "full_pipeline_manifest.json", manifest)
    return output


def extract_latest_stage_manifest(scene_dir: Path, stage: str) -> dict | None:
    metrics_dir = scene_dir / "metrics" / stage
    if not metrics_dir.exists():
        return None
    candidates = sorted(metrics_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not candidates:
        return None
    with candidates[0].open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def parse_3dgs_eval_metrics(output: str) -> list[dict[str, float | int | str | None]]:
    pattern = re.compile(
        r"\[ITER\s+(?P<iteration>\d+)\]\s+Evaluating\s+(?P<split>\w+):\s+"
        r"L1\s+(?P<l1>[-+0-9.eE]+)\s+PSNR\s+(?P<psnr>[-+0-9.eE]+)"
        r"(?:\s+SSIM\s+(?P<ssim>[-+0-9.eE]+))?"
    )
    metrics = []
    for match in pattern.finditer(output):
        metrics.append(
            {
                "iteration": int(match.group("iteration")),
                "split": match.group("split"),
                "l1": float(match.group("l1")),
                "psnr": float(match.group("psnr")),
                "ssim": float(match.group("ssim")) if match.group("ssim") is not None else None,
            }
        )
    return metrics


def sanitize_sugar_camera_name(name: str) -> str:
    suffix = Path(name).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg"}:
        return Path(name).stem
    return name


def copy_file_if_needed(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        src_stat = src.stat()
        dst_stat = dst.stat()
        if src_stat.st_size == dst_stat.st_size and int(src_stat.st_mtime) == int(dst_stat.st_mtime):
            return
    shutil.copy2(src, dst)


def validate_official_sugar_metrics_checkpoint(gs_model_dir: Path) -> None:
    for iteration in (7000, 30000):
        point_cloud = gs_model_dir / "point_cloud" / f"iteration_{iteration}" / "point_cloud.ply"
        if not point_cloud.exists():
            raise FileNotFoundError(
                "Official SuGaR metrics require vanilla 3DGS checkpoints at iterations 7000 and 30000. "
                f"Missing: {point_cloud}"
            )
    cameras_path = gs_model_dir / "cameras.json"
    if not cameras_path.exists():
        raise FileNotFoundError(f"Official SuGaR metrics require cameras.json: {cameras_path}")


def prepare_official_sugar_metrics_checkpoint(gs_model_dir: Path, scene_dir: Path) -> Path:
    validate_official_sugar_metrics_checkpoint(gs_model_dir)
    compat_dir = scene_dir / "gs" / "model_sugar_metrics_compat"
    compat_dir.mkdir(parents=True, exist_ok=True)

    cameras = json.loads((gs_model_dir / "cameras.json").read_text(encoding="utf-8"))
    sanitized_cameras = []
    for camera in cameras:
        new_camera = dict(camera)
        new_camera["img_name"] = sanitize_sugar_camera_name(str(new_camera.get("img_name", "")))
        sanitized_cameras.append(new_camera)
    (compat_dir / "cameras.json").write_text(json.dumps(sanitized_cameras, indent=2), encoding="utf-8")

    for iteration in (7000, 30000):
        copy_file_if_needed(
            gs_model_dir / "point_cloud" / f"iteration_{iteration}" / "point_cloud.ply",
            compat_dir / "point_cloud" / f"iteration_{iteration}" / "point_cloud.ply",
        )
    for optional_name in ("cfg_args", "input.ply", "exposure.json"):
        optional_src = gs_model_dir / optional_name
        if optional_src.exists():
            copy_file_if_needed(optional_src, compat_dir / optional_name)
    return compat_dir


def extra_sugar_tokens(extra_args: list[str]) -> list[str]:
    tokens: list[str] = []
    for extra_arg in extra_args:
        tokens.extend(shlex.split(extra_arg))
    return tokens


def extra_arg_value(tokens: list[str], names: tuple[str, ...]) -> str | None:
    for index, token in enumerate(tokens):
        if token in names and index + 1 < len(tokens):
            return tokens[index + 1]
        for name in names:
            prefix = f"{name}="
            if token.startswith(prefix):
                return token[len(prefix) :]
    return None


def sugar_metrics_parameters(args: argparse.Namespace, preset: PipelinePreset) -> dict[str, str]:
    sugar_mode = preset.sugar_mode if args.sugar_quality_mode == "preset" else args.sugar_quality_mode
    if sugar_mode == "low":
        n_vertices = 200_000
        gaussians_per_triangle = 6
    else:
        n_vertices = 1_000_000
        gaussians_per_triangle = 1

    refinement_iterations_by_time = {"short": 2_000, "medium": 7_000, "long": 15_000}
    refinement_time = args.sugar_refinement_time or preset.sugar_refinement_time
    refinement_iterations = refinement_iterations_by_time[refinement_time]
    surface_level = 0.3

    tokens = extra_sugar_tokens(args.extra_sugar_arg)
    refinement_time_override = extra_arg_value(tokens, ("--refinement_time", "--refinement-time"))
    if refinement_time_override in refinement_iterations_by_time:
        refinement_iterations = refinement_iterations_by_time[refinement_time_override]

    surface_override = extra_arg_value(tokens, ("-l", "--surface_level", "--surface-level"))
    vertices_override = extra_arg_value(tokens, ("-v", "--n_vertices_in_mesh"))
    gaussians_override = extra_arg_value(tokens, ("-g", "--gaussians_per_triangle"))
    refinement_override = extra_arg_value(tokens, ("-f", "--refinement_iterations"))

    if args.surface_level is not None:
        surface_level = args.surface_level
    elif surface_override is not None:
        surface_level = float(surface_override)
    if args.n_vertices is not None:
        n_vertices = args.n_vertices
    elif vertices_override is not None:
        n_vertices = int(vertices_override)
    if args.gaussians_per_triangle is not None:
        gaussians_per_triangle = args.gaussians_per_triangle
    elif gaussians_override is not None:
        gaussians_per_triangle = int(gaussians_override)
    if args.refinement_iterations is not None:
        refinement_iterations = args.refinement_iterations
    elif refinement_override is not None:
        refinement_iterations = int(refinement_override)

    return {
        "surface_level": str(surface_level),
        "n_vertices_in_mesh": str(n_vertices),
        "gaussians_per_triangle": str(gaussians_per_triangle),
        "refinement_iterations": str(refinement_iterations),
    }

def sugar_metric_code(value: str) -> str:
    try:
        numeric = float(value)
        if numeric.is_integer():
            return str(int(numeric))
        return f"{numeric:g}".replace(".", "")
    except ValueError:
        return value.replace(".", "")


def expected_refined_sugar_dir(
    sugar_scene_output_dir: Path,
    scene_name: str,
    regularization_type: str,
    params: dict[str, str],
) -> Path:
    level = sugar_metric_code(params["surface_level"])
    decimation = sugar_metric_code(params["n_vertices_in_mesh"])
    gaussians = sugar_metric_code(params["gaussians_per_triangle"])
    dirname = (
        f"sugarfine_3Dgs7000_{regularization_type}estim02_sdfnorm02_"
        f"level{level}_decim{decimation}_normalconsistency01_gaussperface{gaussians}"
    )
    return sugar_scene_output_dir / "refined" / scene_name / dirname


def sync_refinement_iterations_with_existing_checkpoint(
    sugar_scene_output_dir: Path,
    scene_name: str,
    regularization_type: str,
    params: dict[str, str],
) -> None:
    refined_dir = expected_refined_sugar_dir(sugar_scene_output_dir, scene_name, regularization_type, params)
    requested_path = refined_dir / f"{params['refinement_iterations']}.pt"
    if requested_path.exists():
        return

    same_config_checkpoints = sorted(
        checkpoint for checkpoint in refined_dir.glob("*.pt") if checkpoint.stem.isdigit()
    )
    if len(same_config_checkpoints) == 1:
        params["refinement_iterations"] = same_config_checkpoints[0].stem
        return

    all_checkpoints = sorted(
        checkpoint
        for checkpoint in (sugar_scene_output_dir / "refined" / scene_name).glob("sugarfine_*/*.pt")
        if checkpoint.stem.isdigit()
    )
    found = ", ".join(str(path) for path in all_checkpoints[:10]) or "none"
    raise FileNotFoundError(
        "Official SuGaR metrics require the refined SuGaR checkpoint that matches the metrics parameters. "
        f"Missing: {requested_path}. Found refined checkpoints: {found}. "
        "Pass the matching refinement iterations with --extra-sugar-arg='-f <iterations>' "
        "or evaluate with the preset used for training."
    )


def build_official_sugar_metrics_command(
    args: argparse.Namespace,
    preset: PipelinePreset,
    data_root: Path,
    scene_dir: Path,
    gs_model_dir: Path,
    sugar_output_name: str,
) -> tuple[list[str], Path, Path]:
    source_dir = scene_dir / "gs" / "source"
    compat_dir = prepare_official_sugar_metrics_checkpoint(gs_model_dir, scene_dir)
    metrics_dir = scene_dir / "metrics" / "train_sugar"
    config_path = metrics_dir / f"{sugar_output_name}_official_metrics_config.json"
    source_dir_in_container = f"/data/{source_dir.relative_to(data_root).as_posix()}"
    compat_dir_in_container = f"/data/{compat_dir.relative_to(data_root).as_posix()}/"
    write_json(config_path, {source_dir_in_container: compat_dir_in_container})

    sugar_output_root = resolve_path_under_root(data_root, args.sugar_output_root, "sugar-output-root")
    sugar_scene_output_dir = sugar_output_root / sugar_output_name
    sugar_output_root_in_container = f"/data/{sugar_scene_output_dir.relative_to(data_root).as_posix()}"
    config_path_in_container = f"/data/{config_path.relative_to(data_root).as_posix()}"
    params = sugar_metrics_parameters(args, preset)
    sync_refinement_iterations_with_existing_checkpoint(
        sugar_scene_output_dir,
        source_dir.name,
        args.sugar_regularization,
        params,
    )

    metrics_args = [
        "conda",
        "run",
        "--no-capture-output",
        "-n",
        "sugar",
        "python",
        "metrics.py",
        "--scene_config",
        config_path_in_container,
        "--regularization_type",
        args.sugar_regularization,
        "--surface_level",
        params["surface_level"],
        "--n_vertices_in_mesh",
        params["n_vertices_in_mesh"],
        "--gaussians_per_triangle",
        params["gaussians_per_triangle"],
        "--refinement_iterations",
        params["refinement_iterations"],
        "--evaluate_vanilla",
        "True",
    ]
    shell_command = " && ".join(
        [
            "cd /opt/SuGaR",
            "rm -rf output",
            f"ln -s {shlex.quote(sugar_output_root_in_container)} output",
            shlex.join(metrics_args),
        ]
    )
    command = ["docker", "compose", "run", "--rm", "sugar", "bash", "-lc", shell_command]
    return command, config_path, sugar_scene_output_dir / "metrics"


def main() -> int:
    args = parse_args()
    preset = PRESETS[args.preset]
    data_root = get_data_root()
    root = repo_root()

    run_name = args.run_name or default_run_name()
    job_path = resolve_repo_path(args.job_path, root / "jobs" / "segmentation" / f"{args.scene_name}_job.json")
    mask_output_dir = args.mask_output_dir or f"masks/{args.scene_name}"
    dataset_dir = args.dataset_dir or f"3dgs/{args.scene_name}"
    scene_dir = resolve_path_under_root(data_root, dataset_dir, "dataset-dir")
    gs_model_dir_arg = args.gs_model_dir or f"{Path(dataset_dir).as_posix()}/gs/model"
    gs_model_dir = resolve_path_under_root(data_root, gs_model_dir_arg, "gs-model-dir")
    sugar_output_name = args.sugar_output_name or args.scene_name
    log_dir = root / "logs" / args.scene_name / run_name

    frame_step = args.frame_step or preset.frame_step
    iterations = args.iterations or preset.iterations
    sequential_overlap = args.sequential_overlap or preset.sequential_overlap
    sugar_refinement_time = args.sugar_refinement_time or preset.sugar_refinement_time
    sugar_mode = preset.sugar_mode if args.sugar_quality_mode == "preset" else args.sugar_quality_mode
    skip_sugar = args.skip_sugar or (not preset.run_sugar and not args.run_sugar)
    args.skip_sugar = skip_sugar

    video_path = resolve_path_under_root(data_root, args.video, "video")
    if not video_path.exists():
        raise FileNotFoundError(f"Video file does not exist: {video_path}")
    if args.object_id < 1:
        raise ValueError("--object-id must be greater than or equal to 1.")

    if args.skip_bbox and not job_path.exists():
        raise FileNotFoundError(f"--skip-bbox requires an existing job file: {job_path}")

    if not args.skip_bbox:
        ensure_can_write_stage(job_path, "bbox/job", args.force)
    if not args.skip_segmentation:
        ensure_can_write_stage(resolve_path_under_root(data_root, mask_output_dir, "mask-output-dir"), "segmentation", args.force)
    if not args.skip_prepare:
        ensure_can_write_stage(scene_dir, "prepared dataset", args.force)
    if not args.skip_3dgs:
        ensure_can_write_stage(gs_model_dir, "3DGS model", args.force)

    manifest = {
        "status": "running",
        "started_at": utc_now_iso(),
        "scene_name": args.scene_name,
        "run_name": run_name,
        "preset": args.preset,
        "resolved_parameters": {
            "frame_step": frame_step,
            "iterations": iterations,
            "sequential_overlap": sequential_overlap,
            "matcher": args.matcher,
            "camera_model": args.camera_model,
            "single_camera": args.single_camera,
            "mask_loss": args.mask_loss,
            "metrics": args.metrics,
            "eval_3dgs": args.eval_3dgs,
            "sugar_mode": sugar_mode,
            "sugar_refinement_time": sugar_refinement_time,
            "skip_sugar": skip_sugar,
        },
        "paths": {
            "video": str(video_path),
            "job_path": str(job_path),
            "mask_output_dir": str(resolve_path_under_root(data_root, mask_output_dir, "mask-output-dir")),
            "scene_dir": str(scene_dir),
            "gs_model_dir": str(gs_model_dir),
            "sugar_output_name": sugar_output_name,
            "log_dir": str(log_dir),
        },
        "stages": [],
    }
    log_dir.mkdir(parents=True, exist_ok=True)
    write_json(log_dir / "full_pipeline_manifest.json", manifest)

    try:
        if not args.skip_bbox:
            run_stage(
                build_select_bbox_command(args, root, job_path, mask_output_dir),
                "select_bbox",
                log_dir,
                manifest,
            )

        delegated_return_code = delegate_docker_stages_to_wsl(root, args, job_path, run_name, log_dir, manifest)
        if delegated_return_code is not None:
            return delegated_return_code

        if not args.skip_segmentation:
            remove_if_force(resolve_path_under_root(data_root, mask_output_dir, "mask-output-dir"), args.force)
            run_stage(
                [
                    "docker",
                    "compose",
                    "run",
                    "--rm",
                    "sam2-seg",
                    "python",
                    "/app/scripts/segment_video.py",
                    "--job",
                    job_path_in_container(job_path),
                    "--frame-step",
                    str(frame_step),
                ],
                "segment_video",
                log_dir,
                manifest,
            )

        if not args.skip_prepare:
            prepare_cmd = [
                sys.executable,
                str(root / "scripts" / "prepare_3dgs_dataset.py"),
                "--job",
                str(job_path),
                "--output-dir",
                dataset_dir,
                "--scene-name",
                args.scene_name,
                "--frame-step",
                str(frame_step),
            ]
            if args.mask_loss:
                prepare_cmd.extend(["--gs-image-mode", "original"])
            run_stage(prepare_cmd, "prepare_3dgs_dataset", log_dir, manifest)

        if not args.skip_colmap:
            colmap_cmd = [
                sys.executable,
                str(root / "scripts" / "run_colmap_pipeline.py"),
                "--scene-dir",
                dataset_dir,
                "--matcher",
                args.matcher,
                "--camera-model",
                args.camera_model,
                "--sequential-overlap",
                str(sequential_overlap),
            ]
            if args.single_camera:
                colmap_cmd.append("--single-camera")
            append_optional_bool_arg(colmap_cmd, args.use_gpu, "--use-gpu", "--no-use-gpu")
            append_optional_bool_arg(colmap_cmd, args.use_colmap_masks, "--use-colmap-masks", "--no-use-colmap-masks")
            append_optional_arg(colmap_cmd, "--sparse-model", args.sparse_model)
            if args.skip_feature_extraction:
                colmap_cmd.append("--skip-feature-extraction")
            if args.skip_matching:
                colmap_cmd.append("--skip-matching")
            if args.skip_mapping:
                colmap_cmd.append("--skip-mapping")
            if args.skip_undistort:
                colmap_cmd.append("--skip-undistort")
            run_stage(colmap_cmd, "run_colmap_pipeline", log_dir, manifest)

        if not args.skip_3dgs:
            remove_if_force(gs_model_dir, args.force)
            train_cmd = [
                sys.executable,
                str(root / "scripts" / "train_3dgs.py"),
                "--scene-dir",
                dataset_dir,
                "--model-dir",
                gs_model_dir_arg,
                "--iterations",
                str(iterations),
                "--resolution",
                str(args.resolution),
                "--log-path",
                str(log_dir / "train_3dgs_inner.log"),
            ]
            if args.metrics or args.eval_3dgs:
                train_cmd.append("--eval")
            if args.metrics:
                append_passthrough_arg(train_cmd, "--extra-arg", "--test_iterations")
                append_passthrough_arg(train_cmd, "--extra-arg", str(iterations))
            if args.white_background:
                train_cmd.append("--white-background")
            if args.mask_loss:
                train_cmd.append("--mask-loss")
            append_optional_arg(train_cmd, "--masks-dir", args.masks_dir)
            for extra_arg in args.extra_3dgs_arg:
                append_passthrough_arg(train_cmd, "--extra-arg", extra_arg)
            train_output = run_stage(train_cmd, "train_3dgs", log_dir, manifest)
            manifest["metrics_3dgs_from_log"] = parse_3dgs_eval_metrics(train_output)
            latest_train_manifest = extract_latest_stage_manifest(scene_dir, "train_3dgs")
            if latest_train_manifest is not None:
                manifest["latest_train_3dgs_manifest"] = latest_train_manifest
            write_json(log_dir / "full_pipeline_manifest.json", manifest)

        if not skip_sugar:
            sugar_cmd = [
                sys.executable,
                str(root / "scripts" / "train_sugar.py"),
                "--scene-dir",
                dataset_dir,
                "--gs-model-dir",
                gs_model_dir_arg,
                "--regularization",
                args.sugar_regularization,
                "--sugar-output-root",
                args.sugar_output_root,
                "--sugar-output-name",
                sugar_output_name,
                "--refinement-time",
                sugar_refinement_time,
            ]
            if sugar_mode == "low":
                sugar_cmd.append("--low-poly")
            elif sugar_mode == "high":
                sugar_cmd.append("--high-poly")
            if args.white_background:
                sugar_cmd.append("--white-background")
            append_optional_arg(sugar_cmd, "--surface-level", str(args.surface_level) if args.surface_level is not None else None)
            append_optional_arg(sugar_cmd, "--n-vertices", str(args.n_vertices) if args.n_vertices is not None else None)
            append_optional_arg(sugar_cmd, "--gaussians-per-triangle", str(args.gaussians_per_triangle) if args.gaussians_per_triangle is not None else None)
            append_optional_arg(sugar_cmd, "--refinement-iterations", str(args.refinement_iterations) if args.refinement_iterations is not None else None)
            append_optional_arg(sugar_cmd, "--square-size", str(args.square_size) if args.square_size is not None else None)
            append_optional_arg(sugar_cmd, "--gpu", str(args.sugar_gpu) if args.sugar_gpu is not None else None)
            append_optional_arg(sugar_cmd, "--bboxmin", args.bboxmin)
            append_optional_arg(sugar_cmd, "--bboxmax", args.bboxmax)
            append_optional_bool_arg(sugar_cmd, args.center_bbox, "--center-bbox", "--no-center-bbox")
            append_optional_bool_arg(sugar_cmd, args.export_obj, "--export-obj", "--no-export-obj")
            append_optional_bool_arg(sugar_cmd, args.export_ply, "--export-ply", "--no-export-ply")
            append_optional_bool_arg(sugar_cmd, args.postprocess_mesh, "--postprocess-mesh", "--no-postprocess-mesh")
            append_optional_arg(sugar_cmd, "--postprocess-density-threshold", str(args.postprocess_density_threshold) if args.postprocess_density_threshold is not None else None)
            append_optional_arg(sugar_cmd, "--postprocess-iterations", str(args.postprocess_iterations) if args.postprocess_iterations is not None else None)
            for extra_arg in args.extra_sugar_arg:
                append_passthrough_arg(sugar_cmd, "--extra-arg", extra_arg)
            if args.metrics:
                validate_official_sugar_metrics_checkpoint(gs_model_dir)
            run_stage(sugar_cmd, "train_sugar", log_dir, manifest)
            if args.metrics:
                sugar_metrics_cmd, sugar_metrics_config, sugar_metrics_dir = build_official_sugar_metrics_command(
                    args,
                    preset,
                    data_root,
                    scene_dir,
                    gs_model_dir,
                    sugar_output_name,
                )
                run_stage(sugar_metrics_cmd, "sugar_metrics", log_dir, manifest)
                manifest["official_sugar_metrics"] = {
                    "config_path": str(sugar_metrics_config),
                    "metrics_dir": str(sugar_metrics_dir),
                }
                write_json(log_dir / "full_pipeline_manifest.json", manifest)
        elif args.metrics:
            validate_official_sugar_metrics_checkpoint(gs_model_dir)
            sugar_metrics_cmd, sugar_metrics_config, sugar_metrics_dir = build_official_sugar_metrics_command(
                args,
                preset,
                data_root,
                scene_dir,
                gs_model_dir,
                sugar_output_name,
            )
            run_stage(sugar_metrics_cmd, "sugar_metrics", log_dir, manifest)
            manifest["official_sugar_metrics"] = {
                "config_path": str(sugar_metrics_config),
                "metrics_dir": str(sugar_metrics_dir),
            }
            write_json(log_dir / "full_pipeline_manifest.json", manifest)

        manifest["status"] = "success"
        manifest["finished_at"] = utc_now_iso()
        write_json(log_dir / "full_pipeline_manifest.json", manifest)
        print(f"Full pipeline manifest: {log_dir / 'full_pipeline_manifest.json'}")
        return 0
    except subprocess.CalledProcessError as exc:
        manifest["status"] = "failed"
        manifest["finished_at"] = utc_now_iso()
        manifest["error"] = f"Command failed with exit code {exc.returncode}: {build_command_string(exc.cmd)}"
        write_json(log_dir / "full_pipeline_manifest.json", manifest)
        print(f"[error] {manifest['error']}", file=sys.stderr)
        print(f"Full pipeline manifest: {log_dir / 'full_pipeline_manifest.json'}", file=sys.stderr)
        return int(exc.returncode)
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["finished_at"] = utc_now_iso()
        manifest["error"] = str(exc)
        write_json(log_dir / "full_pipeline_manifest.json", manifest)
        print(f"[error] {exc}", file=sys.stderr)
        print(f"Full pipeline manifest: {log_dir / 'full_pipeline_manifest.json'}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
