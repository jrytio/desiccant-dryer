#!/usr/bin/env bash
# Build the screen-scenarios preview once, then render every scenario through
# the panel's 3-3-2 palette into docs/display/state-NN.png (2x nearest-
# neighbour, so each panel pixel is a crisp 2x2 block). Needs brew sdl2 for
# the build; no window capture is involved.
# Usage: scripts/scenario-shots.sh [first] [last]     (default 1 12)
set -euo pipefail
cd "$(dirname "$0")/.."
first=${1:-1}
last=${2:-12}

esphome compile esphome/desiccant-dryer-scenarios.yaml > /dev/null
BIN=esphome/.esphome/build/desiccant-dryer-scenarios/.pioenvs/desiccant-dryer-scenarios/program
[ -x "$BIN" ] || { echo "scenarios binary not found at $BIN" >&2; exit 1; }
# Pillow comes with ESPHome's own interpreter: read it from the launcher's
# shebang (Homebrew: .../libexec/bin/python), falling back to readlink -f
# (macOS 12.3+, Linux) and then to whatever python3 is on PATH.
ESPHOME=$(command -v esphome)
PY=$(sed -n '1s/^#!//p' "$ESPHOME")
[ -x "$PY" ] || PY="$(dirname "$(readlink -f "$ESPHOME" 2>/dev/null || echo "$ESPHOME")")/python"
[ -x "$PY" ] || PY=$(command -v python3)
"$PY" -c 'import PIL' 2>/dev/null || { echo "$PY has no Pillow; cannot convert PPM to PNG" >&2; exit 1; }
mkdir -p docs/display
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

for n in $(seq "$first" "$last"); do
  out=docs/display/state-$(printf %02d "$n").png
  SCENARIO=$n SHOT="$tmp/shot.ppm" "$BIN" > "$tmp/log.txt" 2>&1 || {
    echo "scenario $n failed:" >&2; tail -5 "$tmp/log.txt" >&2; exit 1; }
  "$PY" - "$tmp/shot.ppm" "$out" <<'EOF'
import sys
from PIL import Image
im = Image.open(sys.argv[1]).convert("RGB")
im.resize((im.width * 2, im.height * 2), Image.NEAREST).save(sys.argv[2])
EOF
  echo "wrote $out"
done
