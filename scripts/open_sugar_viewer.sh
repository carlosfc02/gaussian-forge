#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/open_sugar_viewer.sh --ply-path <path> --source-dir <path> [options]

Options:
  --ply-path <path>          SuGaR refined .ply, absolute or relative to data/.
  --source-dir <path>        Matching 3DGS gs/source directory.
  --base-model-dir <path>    Base 3DGS gs/model directory. Defaults next to source.
  --viewer-model-dir <path>  Temporary viewer model directory. Defaults under data/sugar_output/viewer/.
  --load-images              Ask SIBR to load source images.
  --no-interop               Disable CUDA/OpenGL interop.
  --print-only               Print the docker command without launching it.
EOF
}

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"

ply_path=""
source_dir=""
base_model_dir=""
viewer_model_dir=""
load_images=false
no_interop=false
print_only=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ply-path) ply_path="${2:-}"; shift 2 ;;
    --source-dir) source_dir="${2:-}"; shift 2 ;;
    --base-model-dir) base_model_dir="${2:-}"; shift 2 ;;
    --viewer-model-dir) viewer_model_dir="${2:-}"; shift 2 ;;
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

if [[ -z "${ply_path}" || -z "${source_dir}" ]]; then
  echo "Provide --ply-path and --source-dir." >&2
  exit 2
fi

resolved_ply="$(resolve_data_path "${ply_path}")"
resolved_source="$(resolve_data_path "${source_dir}")"
if [[ ! -f "${resolved_ply}" || "${resolved_ply}" != *.ply ]]; then
  echo "PLY file does not exist or is not a .ply: ${resolved_ply}" >&2
  exit 1
fi
if [[ ! -d "${resolved_source}" ]]; then
  echo "3DGS source directory does not exist: ${resolved_source}" >&2
  exit 1
fi

if [[ -z "${base_model_dir}" ]]; then
  base_model_dir="$(dirname "${resolved_source}")/model"
fi
resolved_base_model="$(resolve_data_path "${base_model_dir}")"
if [[ ! -d "${resolved_base_model}" ]]; then
  echo "Base 3DGS model directory does not exist: ${resolved_base_model}" >&2
  exit 1
fi

if [[ -z "${viewer_model_dir}" ]]; then
  ply_stem="$(basename "${resolved_ply}" .ply)"
  viewer_model_dir="${repo_root}/data/sugar_output/viewer/${ply_stem}"
fi
resolved_viewer_model="$(resolve_data_path "${viewer_model_dir}")"
to_container_data_path "${resolved_viewer_model}" >/dev/null
point_cloud_dir="${resolved_viewer_model}/point_cloud/iteration_0"
mkdir -p "${point_cloud_dir}"
cp "${resolved_ply}" "${point_cloud_dir}/point_cloud.ply"

for filename in cfg_args cameras.json input.ply exposure.json; do
  if [[ -f "${resolved_base_model}/${filename}" ]]; then
    cp "${resolved_base_model}/${filename}" "${resolved_viewer_model}/${filename}"
  fi
done

if [[ ! -f "${resolved_viewer_model}/cfg_args" ]]; then
  echo "Could not prepare viewer model because cfg_args was not found in ${resolved_base_model}." >&2
  exit 1
fi

args=(--model-dir "${resolved_viewer_model}" --source-dir "${resolved_source}" --iteration 0)
if [[ "${load_images}" == true ]]; then
  args+=(--load-images)
fi
if [[ "${no_interop}" == true ]]; then
  args+=(--no-interop)
fi
if [[ "${print_only}" == true ]]; then
  args+=(--print-only)
fi

"${script_dir}/open_3dgs_viewer.sh" "${args[@]}"
