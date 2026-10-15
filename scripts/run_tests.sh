#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
if [ ! -x .venv/bin/python ]; then
    printf '%s\n' 'Missing project environment. Run: uv sync --locked --extra desktop' >&2
    exit 2
fi
export QT_QUICK_BACKEND=${QT_QUICK_BACKEND:-software}
export QT_QUICK_CONTROLS_STYLE=${QT_QUICK_CONTROLS_STYLE:-Basic}
exec xvfb-run -a .venv/bin/python -m pytest "$@"
