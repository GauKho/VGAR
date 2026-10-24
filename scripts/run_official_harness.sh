#!/usr/bin/env bash
# Run from a provisioned Linux harness environment; never start/install Docker.
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${repo_root}/src${PYTHONPATH:+:${PYTHONPATH}}"
export PYTHONUTF8=1
exec "${VGAR_HARNESS_PYTHON:-python3}" -B -m vgar.evaluation.harness.official "$@"
