"""Disposable rehearsal of the pinned operator updater."""
import json, os, shutil, subprocess, sys
from pathlib import Path
import pytest

STAGE_DIR=os.environ.get('STICKY_INTENT_RELEASE_DIR','')
STAGE=Path(STAGE_DIR) if STAGE_DIR else None


def _stage_dir(tmp_path):
    """Rehearsing the real updater needs a staged release to copy."""
    if STAGE is None or not STAGE.is_dir(): pytest.skip('set STICKY_INTENT_RELEASE_DIR to a staged release directory')
    stage=tmp_path/'stage'; shutil.copytree(STAGE,stage); return stage


def test_operator_update_preserves_store_and_refuses_running(tmp_path):
    stage=_stage_dir(tmp_path)
    home=tmp_path/'operator'; (home/'.config').mkdir(parents=True); (home/'.config/autostart').mkdir()
    store=home/'.local/share/sticky-intent/store'; store.mkdir(parents=True)
    (store/'keep.md').write_text('private exact note')
    env={'HOME':str(home),'PATH':os.environ['PATH']}
    r=subprocess.run([sys.executable,str(stage/'install_update.py')],cwd=stage,env=env,capture_output=True,text=True)
    assert r.returncode==0,r.stderr
    assert (store/'keep.md').read_text()=='private exact note'
    receipt=home/'.local/share/sticky-intent/install-0.3.0.json'
    assert receipt.stat().st_mode & 0o777 == 0o600
    data=json.loads(receipt.read_text()); assert data['gui_launched'] is False and data['autostart_modified'] is False
    assert (home/'.local/bin/sticky').stat().st_mode & 0o777 == 0o700
    assert not (home/'.config/autostart/sticky-intent.desktop').exists()


def test_operator_update_refuses_lock(tmp_path):
    stage=_stage_dir(tmp_path)
    home=tmp_path/'operator'; lock=home/'.local/share/sticky-intent/store'; lock.mkdir(parents=True)
    (lock/'widget.lock').write_text('held')
    code='import fcntl,sys; f=open(sys.argv[1],"rb"); fcntl.flock(f,fcntl.LOCK_EX); input()'
    p=subprocess.Popen([sys.executable,'-c',code,str(lock/'widget.lock')],stdin=subprocess.PIPE)
    try:
        import time; time.sleep(.1)
        r=subprocess.run([sys.executable,str(stage/'install_update.py')],cwd=stage,env={'HOME':str(home),'PATH':os.environ['PATH']},capture_output=True,text=True)
        assert r.returncode!=0 and 'REFUSED' in r.stderr
    finally: p.kill();p.wait()
