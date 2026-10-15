"""Rehearse the exact new updater with disposable operator accounts only."""
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import pytest

REPO=Path(__file__).resolve().parents[1]
RELEASE_DIR=os.environ.get('STICKY_INTENT_RELEASE_DIR','')
RELEASE=Path(RELEASE_DIR) if RELEASE_DIR else None

@pytest.fixture
def update_stage(tmp_path,monkeypatch):
    if RELEASE is None or not RELEASE.is_dir(): pytest.skip('set STICKY_INTENT_RELEASE_DIR to a staged release to rehearse the updater')
    stage=tmp_path/'stage'; stage.mkdir()
    shutil.copyfile(REPO/'scripts/install-pocket-update.py',stage/'install_update.py')
    for folder in ['wheelhouse','runtime']:
        (stage/folder).mkdir()
        for source in (RELEASE/folder).iterdir():
            if source.is_file(): os.link(source,stage/folder/source.name)
    home=tmp_path/'operator'; home.mkdir()
    root=home/'.local/share/sticky-intent'; root.mkdir(parents=True)
    env={**os.environ,'HOME':str(home),'STICKY_INTENT_HOME':str(root),'XDG_DATA_HOME':str(home/'.local/share'),'STICKY_TESTING':'1'}
    env.pop('SUDO_UID',None)
    return stage,home,root,env


def invoke(stage,env):
    return subprocess.run([sys.executable,str(stage/'install_update.py')],env=env,capture_output=True,text=True,timeout=90)


def test_update_refuses_actual_store_widget_lock_before_touching_program(update_stage):
    stage,home,root,env=update_stage
    (root/'venv').mkdir(); (root/'venv/untouched').write_text('old program')
    with (root/'widget.lock').open('wb') as locked:
        fcntl.flock(locked,fcntl.LOCK_EX)
        result=invoke(stage,env)
    assert result.returncode!=0 and 'Pocket Notes is open' in result.stderr
    assert (root/'venv/untouched').read_text()=='old program'


def test_active_detached_run_refuses_even_when_widget_is_closed(update_stage):
    stage,home,root,env=update_stage
    (root/'venv').mkdir(); (root/'venv/untouched').write_text('old program')
    (root/'runs').mkdir()
    (root/'runs/active.json').write_text(json.dumps(dict(state='running',pid=os.getpid())))
    result=invoke(stage,env)
    assert result.returncode!=0 and 'agent run is active' in result.stderr
    assert (root/'venv/untouched').read_text()=='old program'


def test_missing_runtime_refuses_before_removal(update_stage):
    stage,home,root,env=update_stage
    (root/'venv').mkdir(); (root/'venv/untouched').write_text('old program')
    (stage/'runtime/libxcb-cursor.so.0').unlink()
    result=invoke(stage,env)
    assert result.returncode!=0 and 'cannot read staged artifact' in result.stderr
    assert (root/'venv/untouched').read_text()=='old program'


def test_update_preserves_actual_root_notes_settings_startup_and_backups(update_stage):
    stage,home,root,env=update_stage
    (root/'venv').mkdir(); (root/'venv/old-program').write_text('recoverable')
    (root/'notes').mkdir(); (root/'notes/1.md').write_text('Exact private note\n')
    (root/'pocket-state.json').write_text('{"mode":"notes"}')
    (root/'config.toml').write_text('[research]\ntimeout_seconds=45\n')
    (home/'.zshrc').write_text('no startup edits')
    autostart=home/'.config/autostart'; autostart.mkdir(parents=True)
    (autostart/'sticky-intent.desktop').write_text('existing startup remains untouched')
    result=invoke(stage,env)
    assert result.returncode==0,result.stdout+result.stderr
    assert 'VERIFIED 0.5.0 package bytes and Qt platform initialisation' in result.stdout
    assert (root/'notes/1.md').read_text()=='Exact private note\n'
    assert (root/'config.toml').read_text()=='[research]\ntimeout_seconds=45\n'
    assert (root/'pocket-state.json').read_text()=='{"mode":"notes"}'
    assert (home/'.zshrc').read_text()=='no startup edits'
    assert (autostart/'sticky-intent.desktop').read_text()=='existing startup remains untouched'
    receipt=json.loads((root/'install-0.5.0.json').read_text())
    assert receipt['version']=='0.5.0' and receipt['protected_before']==receipt['protected_after']
    assert receipt['gui_launched'] is False and receipt['autostart_modified'] is False
    assert (root/'install-0.5.0.json').stat().st_mode&0o777==0o600
    assert (Path(receipt['backup'])/'venv/old-program').read_text()=='recoverable'
    assert (root/'runtime/libxcb-cursor.so.0').stat().st_mode&0o777==0o600
    # Real installed package: full screenshot and the alpha border, no source imports.
    code='''from pathlib import Path
from sticky_intent.store import Store
from sticky_intent.qt_runtime import prepare_qt
prepare_qt()
from PySide6.QtGui import QGuiApplication,QImage
from PySide6.QtTest import QTest
from sticky_intent.qt_widget import create_window
from shiboken6 import delete
store=Store(Path.home()/"render-fixture"); store.add("INSTALLED PACKAGE FIXTURE")
app=QGuiApplication([]); engine,bridge,window=create_window(app,store)
bridge.show("icon"); QTest.qWait(80)
im=window.grabWindow()
assert not im.isNull() and im.pixelColor(0,0).alpha()==0
assert im.save(str(Path.home()/"installed-icon.png"))
bridge.timer.stop(); bridge.poller.stop(); bridge.draft_timer.stop(); delete(engine)
print("INSTALLED NATIVE ICON HAS TRANSPARENT CORNERS")
'''
    rendered=subprocess.run([str(root/'venv/bin/python'),'-I','-c',code],env={**env,'QT_QPA_PLATFORM':'offscreen','QT_QUICK_BACKEND':'software','QT_QUICK_CONTROLS_STYLE':'Basic'},capture_output=True,text=True,timeout=20)
    assert rendered.returncode==0,rendered.stderr
    assert 'TRANSPARENT CORNERS' in rendered.stdout
