#!/usr/bin/env bash
set -euo pipefail

output_root="${SUGAR_OUTPUT_ROOT:-/data/sugar_output}"

mkdir -p "${output_root}"
rm -rf /opt/SuGaR/output
ln -s "${output_root}" /opt/SuGaR/output

exec "$@"
