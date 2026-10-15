"""Additional Qt parity and real single-instance process proofs."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path
import pytest
from test_qt_pocket import qt_ui, named, click, type_text

pytestmark=pytest.mark.gui


def test_research_visible_result_and_full_log_with_fake_runner(qt_ui):
    from PySide6.QtCore import QMetaObject
    from PySide6.QtTest import QTest
    app,s,e,b,w=qt_ui
    script=s.home/'fixture.py'
    script.write_text('import time; time.sleep(.3); print("LOCAL FIXTURE RESULT — not a real agent")')
    (s.home/'config.toml').write_text('[research]\nhermes = '+json.dumps([sys.executable,str(script),'{prompt}'])+'\ntimeout_seconds = 2\n')
    assert b.research('hermes')
    assert not b.research('hermes')
    deadline=time.monotonic()+5
    while time.monotonic()<deadline and b.researchState=='running': QTest.qWait(50)
    assert b.researchState=='done' and 'LOCAL FIXTURE RESULT' in named(w,'editor').property('text')
    assert 'done' in named(w,'noteStatus').property('text')
    assert 'LOCAL FIXTURE RESULT' in b.readLog(b.logs[0]['path'])
    assert b.readLog('/etc/passwd')=='Invalid log path'


def test_drag_is_not_open_and_hud_controls_survive(qt_ui):
    from PySide6.QtCore import Qt, QPoint
    from PySide6.QtTest import QTest
    app,s,e,b,w=qt_ui
    b.show('icon'); QTest.qWait(60)
    origin=(w.x(),w.y())
    QTest.mousePress(w,Qt.LeftButton,Qt.NoModifier,QPoint(40,40))
    QTest.mouseMove(w,QPoint(55,55),20)
    QTest.mouseRelease(w,Qt.LeftButton,Qt.NoModifier,QPoint(55,55))
    QTest.qWait(60)
    assert b.mode=='icon'
    assert (w.x(),w.y()) != origin
    b.show('notes'); b.preference('interface_size',200); b.show('hud'); QTest.qWait(60)
    assert b.mode=='hud' and w.flags() & Qt.WindowStaysOnTopHint
    c=named(w,'closeWindow'); rect=c.mapRectToScene(c.boundingRect())
    assert rect.bottom()<=w.height()
    click(w,'windowMenu')
    settings=named(w,'settingsScreen')
    assert settings.property('visible') and settings.property('height')>100


def test_preferences_checkpoint_and_dirty_restart(qt_ui):
    from sticky_intent.pocket import PocketController
    from PySide6.QtTest import QTest
    app,s,e,b,w=qt_ui
    b.preference('theme','retro'); b.preference('font_family','Noto Serif')
    b.edit('Recovered local text'); b.checkpoint()
    c=PocketController(s)
    assert c.body=='Recovered local text'
    assert c.preferences['theme']=='retro' and c.dirty
    b.show('capture'); b.editDraft('Persistent capture'); b.checkpoint()
    c=PocketController(s)
    assert c.capture_draft=='Persistent capture'


def test_native_process_raise_under_100ms_and_clean_shutdown(tmp_path):
    pytest.importorskip('PySide6')
    home=tmp_path/'owned'; home.mkdir()
    env=os.environ.copy(); env.update(HOME=str(home),STICKY_INTENT_HOME=str(home/'store'),STICKY_TESTING='1',QT_QUICK_BACKEND='software',QT_QUICK_CONTROLS_STYLE='Basic')
    # A short-lived driver creates the actual Qt window with the real kernel lock.
    code='''from sticky_intent.store import Store
from sticky_intent.instance import WidgetInstance
from sticky_intent.qt_widget import create_window
from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import QTimer
from shiboken6 import delete
s=Store(); own=WidgetInstance(s.home); assert own.acquire()
a=QGuiApplication([]);e,b,w=create_window(a,s,own);own.ready()
QTimer.singleShot(5000,a.quit);a.exec()
b.timer.stop();b.poller.stop();b.draft_timer.stop();delete(e);own.close()
'''
    proc=subprocess.Popen([sys.executable,'-c',code],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        ready=home/'store/widget-ready.json';deadline=time.monotonic()+3
        while not ready.exists() and time.monotonic()<deadline: time.sleep(.02)
        assert ready.exists(), proc.poll()
        start=time.perf_counter()
        result=subprocess.run([sys.executable,'-m','sticky_intent','widget','--renderer','qt','--if-not-running'],env=env,capture_output=True,text=True,timeout=3)
        elapsed=time.perf_counter()-start
        assert result.returncode==0 and elapsed<.1,(elapsed,result.stderr)
        deadline=time.monotonic()+2
        while time.monotonic()<deadline and json.loads(ready.read_text())['raises']==0: time.sleep(.02)
        assert json.loads(ready.read_text())['raises']>0
        out,err=proc.communicate(timeout=8)
        assert proc.returncode==0 and 'TypeError' not in err,(out,err)
        assert not ready.exists()
        print('Qt second launch seconds:',elapsed)
    finally:
        if proc.poll() is None: proc.terminate();proc.communicate(timeout=3)
