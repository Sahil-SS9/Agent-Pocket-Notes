"""Clipboard commands are argv-only. Tk lives in the separate widget module."""
from __future__ import annotations
import os
import shutil
import subprocess
import sys


def has_display():
    return sys.platform in {'darwin','win32'} or bool(os.getenv('DISPLAY') or os.getenv('WAYLAND_DISPLAY'))


def commands(write=False):
    candidates = [('wl-copy',[]) , ('xclip',['-selection','clipboard']), ('pbcopy',[])] if write else [
        ('wl-paste',['--no-newline']),('xclip',['-selection','clipboard','-o']),('pbpaste',[])]
    for name,args in candidates:
        exe=shutil.which(name)
        if exe:
            yield [exe,*args]
    for name in ('pwsh','powershell'):
        exe=shutil.which(name)
        if exe:
            script='Set-Clipboard -Value ([Console]::In.ReadToEnd())' if write else '[Console]::Out.Write((Get-Clipboard -Raw))'
            yield [exe,'-NoProfile','-NonInteractive','-Command',script]


def backend_name():
    if has_display():
        return 'Tk (display; command fallback if unavailable)'
    return next((argv[0] for argv in commands()),'unavailable')


def _transfer(text=None):
    write=text is not None
    errors=[]
    options=[]
    if has_display():
        options.append([sys.executable,'-m','sticky_intent.widget','--clipboard-write' if write else '--clipboard-read'])
    options.extend(commands(write))
    for argv in options:
        try:
            result=subprocess.run(argv,input=text if write else None,capture_output=True,text=True,timeout=3,shell=False)
            if result.returncode==0:
                return result.stdout
            errors.append(result.stderr.strip())
        except (OSError,subprocess.TimeoutExpired) as exc:
            errors.append(str(exc))
    detail='; '.join(e for e in errors if e)
    raise RuntimeError('No clipboard backend available. Install wl-clipboard/xclip, or use a working display.'+(' '+detail if detail else ''))


def read_clipboard():
    return _transfer()


def write_clipboard(text):
    _transfer(text)
