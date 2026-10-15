#!/usr/bin/env python3
"""Offline, note-safe 0.5.0 update. No sudo, startup changes, credentials or GUI."""
from __future__ import annotations
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

VERSION='0.5.0'
ARTIFACTS={
    'wheelhouse/sticky_intent-0.5.0-py3-none-any.whl':'41473899c4daab345f937963092bc3e88a48ef60d0b4b96e78bee11eda2366f3',
    'wheelhouse/pyside6_essentials-6.12.0-cp310-abi3-manylinux_2_34_x86_64.whl':'16f4b5e41daf49235ae048458243da9efe5f3d8040f9cc5aa454ce69893d3bd9',
    'wheelhouse/shiboken6-6.12.0-cp310-abi3-manylinux_2_34_x86_64.whl':'3bde565bb0890044b5c7f63808adddede5abc241e9395a2bfed61919884d6240',
    'runtime/libxcb-cursor.so.0':'10fc489c85d5a208843437d4a9b8867b9599b29a1b0a8e864afa79dca141aceb',
}

def digest(path):
    with path.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()

def atomic(path,data,mode=0o600):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.'+path.name+'-',dir=path.parent)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,'wb') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name): os.unlink(name)

def snapshot(roots):
    result={}
    for root in roots:
        if root.is_symlink(): raise SystemExit('REFUSED: protected path is symlinked: '+str(root))
        if not root.exists(): result[str(root)]='absent'; continue
        files=[root] if root.is_file() else root.rglob('*')
        for p in files:
            relative=p.relative_to(root) if root.is_dir() else Path(p.name)
            if any(x in {'venv','runtime','widget.lock','store.lock'} or x.startswith(('.update-','.previous-','install-')) for x in relative.parts): continue
            if p.is_symlink(): raise SystemExit('REFUSED: protected file is symlinked: '+str(p))
            if p.is_file(): result[str(p)]=digest(p)
    return result

def verify_package(python,wheel,env):
    code='''import hashlib,json,sys,zipfile
from pathlib import Path
from importlib.metadata import version
import sticky_intent
assert version("sticky-intent")=="0.5.0"
root=Path(sticky_intent.__file__).parent.parent
with zipfile.ZipFile(sys.argv[1]) as archive:
    for name in archive.namelist():
        if name.startswith("sticky_intent/") and not name.endswith("/"):
            assert (root/name).read_bytes()==archive.read(name),name
from sticky_intent.qt_runtime import prepare_qt
prepare_qt()
from PySide6.QtGui import QGuiApplication
app=QGuiApplication([])
from PySide6.QtQml import QQmlApplicationEngine
engine=QQmlApplicationEngine()
print("VERIFIED 0.5.0 package bytes and Qt platform initialisation")
'''
    subprocess.run([str(python),'-I','-c',code,str(wheel)],env={**env,'QT_QPA_PLATFORM':'offscreen'},check=True)

def main():
    if os.getuid()==0 or os.geteuid()!=os.getuid() or os.getenv('SUDO_UID'):
        raise SystemExit('REFUSED: run from your normal desktop-user terminal, without sudo.')
    if sys.version_info<(3,12): raise SystemExit('REFUSED: Python 3.12 or newer is required.')
    home=Path.home()
    root=home/'.local/share/sticky-intent'
    wrapper=home/'.local/bin/sticky'
    for path in [home,home/'.local',home/'.local/share',root,root/'venv',root/'runtime',home/'.local/bin',wrapper]:
        if path.is_symlink(): raise SystemExit('REFUSED: symlinked install path: '+str(path))
    stage=Path(__file__).resolve().parent
    # Readability and identities checked BEFORE any installed program is touched.
    for rel,expected in ARTIFACTS.items():
        p=stage/rel
        try: actual=digest(p)
        except OSError as exc: raise SystemExit('REFUSED: cannot read staged artifact '+str(p)+': '+str(exc))
        if actual!=expected: raise SystemExit('REFUSED: artifact checksum mismatch: '+rel)
    root.mkdir(parents=True,exist_ok=True,mode=0o700)
    store=Path(os.getenv('STICKY_INTENT_HOME') or Path(os.getenv('XDG_DATA_HOME') or home/'.local/share')/'sticky-intent').expanduser()
    stores={root,store,root/'store'}
    held=[]
    try:
        for directory in stores:
            if directory.is_symlink(): raise SystemExit('REFUSED: symlinked note store: '+str(directory))
            if not directory.exists(): continue
            lock=directory/'widget.lock'
            fd=os.open(lock,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600); held.append(fd)
            try: fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError: raise SystemExit('REFUSED: Pocket Notes is open. Save and quit it, then rerun this command.')
        for directory in stores:
            for receipt in (directory/'runs').glob('*.json'):
                if receipt.is_symlink(): raise SystemExit('REFUSED: symlinked run receipt')
                try:
                    job=json.loads(receipt.read_bytes())
                    if not isinstance(job,dict) or job.get('state') not in {'queued','running'}: continue
                    pid=job.get('pid')
                    if not pid and receipt.with_suffix('.pid').exists(): pid=int(receipt.with_suffix('.pid').read_text())
                    if type(pid) is not int or pid<=0: raise SystemExit('REFUSED: unfinished agent work has no verifiable supervisor. Open Pocket Notes and inspect/recover it before updating.')
                    try: os.kill(pid,0)
                    except ProcessLookupError: continue
                    except PermissionError: pass
                    raise SystemExit('REFUSED: an agent run is active. Wait for it to finish, then quit Pocket Notes and rerun.')
                except (OSError,ValueError): raise SystemExit('REFUSED: could not verify unfinished agent work')
        protected=[*stores,home/'.bashrc',home/'.zshrc',home/'.config/autostart',home/'.config/sticky-intent']
        before=snapshot(protected)
        candidate=Path(tempfile.mkdtemp(prefix='.update-0.5.0-',dir=root))
        newvenv=candidate/'venv'; newruntime=candidate/'runtime'; newruntime.mkdir(mode=0o700)
        library=newruntime/'libxcb-cursor.so.0'
        shutil.copyfile(stage/'runtime/libxcb-cursor.so.0',library); library.chmod(0o600)
        env={k:v for k,v in os.environ.items() if k not in {'PYTHONPATH','PYTHONHOME','VIRTUAL_ENV','UV_LOCKED','UV_FROZEN','TMPDIR','TMP','TEMP','PIP_TARGET','PIP_PREFIX','PIP_USER'}}
        env.update(HOME=str(home),TMPDIR=str(candidate),PIP_CONFIG_FILE=os.devnull,PIP_CACHE_DIR=str(candidate/'pip-cache'),STICKY_INTENT_QT_RUNTIME=str(newruntime))
        print('Preparing verified Pocket Notes 0.5.0; existing notes and app remain intact...',flush=True)
        subprocess.run([sys.executable,'-m','venv',str(newvenv)],env=env,check=True)
        wheels=[str(stage/p) for p in ARTIFACTS if p.endswith('.whl')]
        subprocess.run([str(newvenv/'bin/python'),'-m','pip','install','--no-index','--no-deps',*wheels],env=env,check=True)
        verify_package(newvenv/'bin/python',stage/'wheelhouse/sticky_intent-0.5.0-py3-none-any.whl',env)
        backup=root/('.previous-0.5.0-'+candidate.name.removeprefix('.update-0.5.0-')); backup.mkdir(mode=0o700)
        if wrapper.exists(): shutil.copyfile(wrapper,backup/'sticky-wrapper'); (backup/'sticky-wrapper').chmod(0o700)
        promoted=[]; moved=[]
        try:
            for name in ['venv','runtime']:
                final=root/name
                if final.exists(): final.rename(backup/name); moved.append(name)
                (candidate/name).rename(final); promoted.append(name)
            atomic(wrapper,('#!/bin/sh\nexec "'+str(root/'venv/bin/python')+'" -m sticky_intent "$@"\n').encode(),0o700)
            after=snapshot(protected)
            if before!=after: raise RuntimeError('Protected note/settings/startup files changed')
            installed_env={**env,'STICKY_INTENT_QT_RUNTIME':str(root/'runtime')}
            verify_package(root/'venv/bin/python',stage/'wheelhouse/sticky_intent-0.5.0-py3-none-any.whl',installed_env)
            atomic(root/'install-0.5.0.json',json.dumps(dict(version=VERSION,artifacts=ARTIFACTS,operator_uid=os.getuid(),venv=str(root/'venv'),backup=str(backup),protected_before=before,protected_after=after,gui_launched=False,autostart_modified=False),indent=2).encode())
        except BaseException:
            for name in reversed(promoted): (root/name).rename(candidate/(name+'-failed'))
            for name in moved: (backup/name).rename(root/name)
            if (backup/'sticky-wrapper').exists(): atomic(wrapper,(backup/'sticky-wrapper').read_bytes(),0o700)
            elif wrapper.exists(): wrapper.unlink()
            raise
        print('UPDATED 0.5.0. Notes/settings preserved. Previous program retained at '+str(backup),flush=True)
    finally:
        for fd in held: os.close(fd)

if __name__=='__main__': main()
