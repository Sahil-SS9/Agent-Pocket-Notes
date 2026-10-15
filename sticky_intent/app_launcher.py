"""Linux app-menu launcher. Explicit install only; never autostart or a GUI import."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from .io import FileLock, atomic_write


def _paths():
    data = Path(os.getenv('XDG_DATA_HOME') or Path.home()/'.local/share')
    state = Path(os.getenv('XDG_STATE_HOME') or Path.home()/'.local/state')
    return (data/'applications/sticky-intent.desktop',
            data/'icons/hicolor/scalable/apps/sticky-intent.svg',
            state/'sticky-intent/desktop-launcher.json')


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _quoted_exec(path):
    value = str(path)
    if any(c in value for c in ('\n', '\r', '\0')):
        raise ValueError('Executable path cannot contain line breaks')
    # Desktop Exec has its own quoting rules; it is not a shell command.
    value = value.replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%')
    return '"' + value + '"'


def install_launcher(*, executable=None):
    if sys.platform != 'linux':
        raise ValueError('This app-menu installer currently supports Linux only')
    selected = str(executable) if executable is not None else shutil.which('sticky')
    if not selected:
        raise ValueError('Install sticky first, or supply --executable with its absolute path')
    executable = Path(selected).absolute()
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise ValueError('The sticky executable is not available')
    target, icon, journal = _paths()
    icon_data = (Path(__file__).parent/'assets/sticky-intent.svg').read_bytes()
    content = ('[Desktop Entry]\nType=Application\nName=Sticky Intent\n'
               'Comment=Local notes for your ideas and agent chats\n'
               f'Exec={_quoted_exec(executable)} widget --background\n'
               f'Icon={icon}\nTerminal=false\nStartupNotify=false\n'
               'StartupWMClass=Stickyintent\nCategories=Utility;\n'
               'Keywords=notes;sticky;ideas;\nX-Sticky-Intent-Managed=true\n').encode()
    payloads = {str(target): content, str(icon): icon_data}
    with FileLock(journal.parent/'desktop-launcher.lock'):
        records = json.loads(journal.read_bytes()) if journal.exists() else {}
        # Preflight every owned file before touching any of them.
        for name in payloads:
            path = Path(name)
            if path.exists():
                if name not in records:
                    raise ValueError(f'An unmanaged launcher file exists: {path}')
                if _hash(path.read_bytes()) != records[name]:
                    raise ValueError(f'Launcher file was edited: {path}; leaving your changes untouched')
        records = {name: _hash(data) for name, data in payloads.items()}
        atomic_write(journal, json.dumps(records).encode())
        for name, data in payloads.items():
            atomic_write(Path(name), data, mode=0o644)
    return f'Application launcher installed: {target}. Search for Sticky Intent in your app menu.'


def uninstall_launcher():
    target, icon, journal = _paths()
    with FileLock(journal.parent/'desktop-launcher.lock'):
        if not journal.exists():
            return 'Application launcher not installed'
        records = json.loads(journal.read_bytes())
        allowed = {str(target), str(icon)}
        if not isinstance(records, dict) or set(records) != allowed:
            raise ValueError('Invalid launcher receipt; refusing to remove files')
        for name, expected in records.items():
            path = Path(name)
            if path.exists() and _hash(path.read_bytes()) != expected:
                raise ValueError(f'Launcher file was edited: {path}; leaving your changes untouched')
        for name in records:
            Path(name).unlink(missing_ok=True)
        journal.unlink()
    return 'Application launcher removed; notes and the installed CLI are unchanged'
