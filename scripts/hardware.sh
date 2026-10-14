#!/usr/bin/env bash
# scripts/hardware.sh — run the board generator with KiCad's own Python.
#   scripts/hardware.sh env|test|generate|route|check|export
# KiCad's bundled interpreter has pcbnew; a plain python3 does not. In the
# kicad/kicad Docker image (CI) python3 is that interpreter.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${KICAD_PYTHON:-}"
if [[ -z "$PY" ]]; then
  for c in /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 /usr/bin/python3; do
    if [[ -x "$c" ]] && "$c" -c 'import pcbnew' 2>/dev/null; then PY="$c"; break; fi
  done
fi
[[ -n "$PY" ]] || { echo "no Python with pcbnew found; install KiCad or set KICAD_PYTHON" >&2; exit 1; }
export PYTHONPATH="hardware${PYTHONPATH:+:$PYTHONPATH}"
exec "$PY" -m dryer_board "$@" 2> >(grep -v 'assert ""traits"" failed' >&2)
