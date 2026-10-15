#!/bin/sh
set -eu
if [ "$(id -u)" = 0 ] || [ -n "${SUDO_UID-}" ]; then
    printf '%s\n' 'Run this as your normal desktop user, without sudo. It installs into the account that runs it.' >&2
    exit 2
fi
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
# Python needs read permission, not an executable installer bit.
python3 "$HERE/install_update.py"
printf '%s\n' 'Launching Pocket Notes 0.5.0 (Qt)...'
exec "$HOME/.local/bin/sticky" widget --renderer qt --if-not-running
