#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/open_3dgs_viewer.sh (--scene-dir <path> | --model-dir <path> --source-dir <path>) [options]

Options:
  --scene-dir <path>    Scene directory relative to data/, for example 3dgs/wood_star.
  --model-dir <path>    3DGS model directory, absolute or relative to data/.
  --source-dir <path>   3DGS source directory, absolute or relative to data/.
  --iteration <number>  Viewer iteration to load.
  --load-images         Ask SIBR to load source images.
  --no-interop          Disable CUDA/OpenGL interop.
  --print-only          Print the docker command without launching it.
EOF
}

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"

scene_dir=""
model_dir=""
source_dir=""
iteration=""
load_images=false
no_interop=false
print_only=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --scene-dir) scene_dir="${2:-}"; shift 2 ;;
    --model-dir) model_dir="${2:-}"; shift 2 ;;
    --source-dir) source_dir="${2:-}"; shift 2 ;;
    --iteration) iteration="${2:-}"; shift 2 ;;
    --load-images) load_images=true; shift ;;
    --no-interop) no_interop=true; shift ;;
    --print-only) print_only=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

resolve_data_path() {
  local input="$1"
  if [[ -z "${input}" ]]; then
    return 1
  fi
  if [[ "${input}" = /* ]]; then
    realpath -m "${input}"
    return 0
  fi
  if [[ -e "${repo_root}/data/${input}" ]]; then
    realpath -m "${repo_root}/data/${input}"
    return 0
  fi
  realpath -m "${repo_root}/${input}"
}

to_container_data_path() {
  local host_path
  host_path="$(realpath -m "$1")"
  case "${host_path}" in
    "${repo_root}/data"/*) printf '/data/%s\n' "${host_path#"${repo_root}/data/"}" ;;
    *) echo "Path must be under ${repo_root}/data because the viewer container only mounts data/: ${host_path}" >&2; exit 1 ;;
  esac
}

if [[ -n "${scene_dir}" ]]; then
  scene_root="$(resolve_data_path "${scene_dir}")"
  if [[ -z "${model_dir}" ]]; then
    model_dir="${scene_root}/gs/model"
  fi
  if [[ -z "${source_dir}" ]]; then
    source_dir="${scene_root}/gs/source"
  fi
fi

if [[ -z "${model_dir}" || -z "${source_dir}" ]]; then
  echo "Provide --scene-dir or both --model-dir and --source-dir." >&2
  exit 2
fi

model_path="$(resolve_data_path "${model_dir}")"
source_path="$(resolve_data_path "${source_dir}")"

if [[ ! -d "${model_path}" ]]; then
  echo "3DGS model directory does not exist: ${model_path}" >&2
  exit 1
fi
if [[ ! -d "${source_path}" ]]; then
  echo "3DGS source directory does not exist: ${source_path}" >&2
  exit 1
fi
if [[ "${print_only}" != true ]]; then
  if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is not available in PATH." >&2
    exit 1
  fi
  if [[ -z "${DISPLAY:-}" ]]; then
    echo "DISPLAY is not set. Start WSLg/X11 before launching the viewer." >&2
    exit 1
  fi
  if ! docker image inspect tfg/3dgs-viewer:latest >/dev/null 2>&1; then
    echo "Docker image tfg/3dgs-viewer:latest is not built. Run: docker compose build viewer" >&2
    exit 1
  fi
fi

viewer_args=(-m "$(to_container_data_path "${model_path}")" -s "$(to_container_data_path "${source_path}")")
if [[ -n "${iteration}" ]]; then
  viewer_args+=(--iteration "${iteration}")
fi
if [[ "${load_images}" == true ]]; then
  viewer_args+=(--load_images)
fi
if [[ "${no_interop}" != true ]] && grep -qiE 'microsoft|wsl' /proc/version 2>/dev/null; then
  no_interop=true
  echo "WSL detected; adding --no_interop to avoid CUDA/OpenGL interop warnings."
fi
if [[ "${no_interop}" == true ]]; then
  viewer_args+=(--no_interop)
fi

command=(docker compose run --rm -d viewer "${viewer_args[@]}")
printf 'Launching 3DGS viewer with Docker:\n  %q' "${command[0]}"
printf ' %q' "${command[@]:1}"
printf '\n'

if [[ "${print_only}" == true ]]; then
  exit 0
fi

cd "${repo_root}"
"${command[@]}"
