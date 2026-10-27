#!/usr/bin/env bash
# Build the mypy/Ruff bundle that DockerExecutor copies into SWE-bench containers.
# Versions come from configs/m2/static/tools.lock.json. Run on the Linux/WSL host
# that runs Docker; needs uv and network. Output: $VGAR_STATIC_TOOLS
# (default ~/.cache/vgar/static-tools).
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
LOCK="$ROOT/configs/m2/static/tools.lock.json"
OUT=${VGAR_STATIC_TOOLS:-$HOME/.cache/vgar/static-tools}
field() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$LOCK" "$1"; }
PYTHON=$(field python) MYPY=$(field mypy) RUFF=$(field ruff)

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
uv python install "$PYTHON" --install-dir "$WORK/pbs" --no-bin
mkdir -p "$WORK/tools/bin"
cp -a "$(readlink -f "$(ls -d "$WORK"/pbs/cpython-"$PYTHON"-linux-x86_64-gnu | head -1)")" "$WORK/tools/py"
uv pip install --python "$WORK/tools/py/bin/python3" --break-system-packages "mypy==$MYPY"
uv pip install --target "$WORK/ruff" --python-platform x86_64-unknown-linux-musl "ruff==$RUFF"
cp "$WORK/ruff/bin/ruff" "$WORK/tools/bin/ruff"

observed_python=$("$WORK/tools/py/bin/python3" -c 'import platform; print(platform.python_version())')
observed_mypy=$("$WORK/tools/py/bin/python3" -m mypy --version | awk '{print $2}')
observed_ruff=$("$WORK/tools/bin/ruff" --version | awk '{print $2}')
packages=$(uv pip freeze --python "$WORK/tools/py/bin/python3" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read().splitlines()))')
cat > "$WORK/tools/manifest.json" <<EOF
{"python": "$observed_python", "mypy": "$observed_mypy", "ruff": "$observed_ruff", "packages": $packages}
EOF
# Container root runs with --cap-drop ALL, so every file must be world-readable.
chmod -R a+rX "$WORK/tools"

rm -rf "$OUT"
mkdir -p "$(dirname "$OUT")"
mv "$WORK/tools" "$OUT"
echo "static tools: $OUT"
cat "$OUT/manifest.json"
