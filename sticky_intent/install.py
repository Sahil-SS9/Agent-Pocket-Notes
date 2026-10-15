"""Explicit, reversible rc/login autostart installation. All paths follow HOME/XDG."""
from __future__ import annotations
import base64
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import stat
import subprocess
import sys
from .io import FileLock, atomic_write
from .store import Store

START='# >>> sticky-intent >>>'
END='# <<< sticky-intent <<<'


def shell_path(shell):
    home=Path.home()
    if shell=='bash': return home/'.bashrc'
    if shell=='zsh': return home/'.zshrc'
    if shell=='fish': return Path(os.getenv('XDG_CONFIG_HOME') or home/'.config')/'fish/config.fish'
    if shell=='pwsh':
        explicit=os.getenv('STICKY_PWSH_PROFILE')
        if explicit: return Path(explicit).expanduser()
        exe=shutil.which('pwsh') or shutil.which('powershell')
        if exe:
            result=subprocess.run([exe,'-NoProfile','-NonInteractive','-Command','[Console]::Out.Write($PROFILE)'],capture_output=True,text=True,timeout=5)
            if result.returncode==0 and result.stdout.strip(): return Path(result.stdout.strip())
        return home/'Documents/PowerShell/Microsoft.PowerShell_profile.ps1'
    raise ValueError('Shell must be bash, zsh, fish or pwsh')


def shell_block(shell,*,platform=None):
    platform=platform or sys.platform
    display='[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]' if platform not in {'darwin','win32'} else 'true'
    command='command sticky widget --background --if-not-running >/dev/null 2>&1 &'
    if shell in {'bash','zsh'}:
        body=f'case $- in\n  *i*)\n    if {display}; then\n      {command}\n    fi\n    ;;\nesac'
    elif shell=='fish':
        guard='test -n "$DISPLAY$WAYLAND_DISPLAY"' if platform not in {'darwin','win32'} else 'true'
        body=f'if status is-interactive\n    if {guard}\n        {command}\n    end\nend'
    elif shell=='pwsh':
        display_ps='($env:DISPLAY -or $env:WAYLAND_DISPLAY)' if platform not in {'darwin','win32'} else '$true'
        hidden=' -WindowStyle Hidden' if platform=='win32' else ''
        body=f"if ([Environment]::UserInteractive -and -not [Console]::IsInputRedirected -and {display_ps}) {{\n    Start-Process -FilePath 'sticky' -ArgumentList @('widget', '--background', '--if-not-running'){hidden} -ErrorAction SilentlyContinue | Out-Null\n}}"
    else:
        raise ValueError('Unknown shell')
    return START+'\n'+body+'\n'+END+'\n'


def login_path(platform=None):
    platform=platform or sys.platform
    home=Path.home()
    if platform=='darwin': return home/'Library/LaunchAgents/com.sticky-intent.widget.plist'
    if platform=='win32': return Path(os.getenv('APPDATA') or home/'AppData/Roaming')/'Microsoft/Windows/Start Menu/Programs/Startup/sticky-intent.cmd'
    return Path(os.getenv('XDG_CONFIG_HOME') or home/'.config')/'autostart/sticky-intent.desktop'


def _login_content(platform):
    executable=shutil.which('sticky') or 'sticky'
    args=[executable,'widget','--background','--if-not-running']
    if platform=='darwin':
        return plistlib.dumps({'Label':'com.sticky-intent.widget','ProgramArguments':args,'RunAtLoad':True})
    if platform=='win32':
        return (f'@echo off\r\nstart "" /B "{executable}" widget --background --if-not-running >NUL 2>&1\r\n').encode()
    quoted='"'+executable.replace('\\','\\\\').replace('"','\\"')+'"'
    return (f'[Desktop Entry]\nType=Application\nName=Sticky Intent\nComment=Your local sticky board\nExec={quoted} widget --background --if-not-running\nTerminal=false\nX-GNOME-Autostart-enabled=true\n').encode()


def _journal():
    return Store().home/'installs/autostart.json'


def install_autostart(*,shell=None,login=False,platform=None):
    if bool(shell)==bool(login): raise ValueError('Choose exactly one shell or --login')
    platform=platform or sys.platform
    path=login_path(platform) if login else shell_path(shell)
    journal=_journal()
    with FileLock(journal.parent/'autostart.lock'):
        records=json.loads(journal.read_bytes()) if journal.exists() else {}
        key=str(path)
        if key in records:
            return f'Autostart already installed: {path}'
        original=path.read_bytes() if path.exists() else None
        mode=stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
        if login:
            added=None; installed=_login_content(platform)
        else:
            if original and (START.encode() in original or END.encode() in original):
                raise ValueError('An unmanaged sticky-intent rc block already exists')
            separator=b'\n' if original and not original.endswith(b'\n') else b''
            added=separator+shell_block(shell,platform=platform).encode()
            installed=(original or b'')+added
        records[key]={'original':base64.b64encode(original).decode() if original is not None else None,
                      'added':base64.b64encode(added).decode() if added is not None else None,
                      'hash':hashlib.sha256(installed).hexdigest(),'mode':mode,'kind':'login' if login else shell}
        # Original bytes are durable before writing the startup target.
        atomic_write(journal,json.dumps(records).encode())
        atomic_write(path,installed,mode=mode)
    return f'Autostart installed: {path}'


def uninstall_autostart():
    journal=_journal()
    with FileLock(journal.parent/'autostart.lock'):
        if not journal.exists(): return 'Autostart not installed'
        records=json.loads(journal.read_bytes())
        planned=[]
        for key,record in records.items():
            path=Path(key); data=path.read_bytes() if path.exists() else None
            if data is None: planned.append((path,None,record['mode'])); continue
            original=base64.b64decode(record['original']) if record['original'] is not None else None
            if hashlib.sha256(data).hexdigest()==record['hash']:
                restored=original
            elif record['added'] is not None:
                added=base64.b64decode(record['added'])
                if data.count(added)!=1: raise ValueError(f'Autostart block was edited: {path}; refusing to remove user changes')
                restored=data.replace(added,b'',1)
                if restored==b'' and original is None: restored=None
            else:
                raise ValueError(f'Login autostart file was edited: {path}; refusing to remove user changes')
            planned.append((path,restored,record['mode']))
        # Validate every target before changing any of them.
        for path,restored,mode in planned:
            if restored is None: path.unlink(missing_ok=True)
            else: atomic_write(path,restored,mode=mode)
        journal.unlink()
    return 'Autostart removed; original bytes restored (unrelated edits preserved)'
