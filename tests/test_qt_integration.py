import builtins
import os
import subprocess
import sys
from sticky_intent.instance import WidgetInstance
from sticky_intent.store import Store


def test_renderer_choice_and_invalid_renderer(monkeypatch):
    from sticky_intent import instance
    assert instance.renderer_choice('qt') == 'qt'
    assert instance.renderer_choice('tk') == 'tk'
    monkeypatch.setenv('STICKY_INTENT_RENDERER','tk')
    assert instance.renderer_choice(None) == 'tk'
    import pytest
    with pytest.raises(ValueError): instance.renderer_choice('invalid')


def test_qt_fast_raise_forbids_toolkit_imports():
    owner=WidgetInstance(Store().home); assert owner.acquire(); owner.ready()
    code='''import builtins
from sticky_intent.boot import main
original=builtins.__import__
def guarded(name,*args,**kwargs):
 if name.startswith(('PySide6','tkinter','sticky_intent.qt_widget')): raise ImportError('GUI imported in fast raise')
 return original(name,*args,**kwargs)
builtins.__import__=guarded
raise SystemExit(main(['widget','--renderer','qt','--if-not-running']))
'''
    try:
        result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=3)
        assert result.returncode==0,result.stderr
        assert owner.poll_raise()
    finally: owner.close()


def test_headless_cli_has_no_gui_modules():
    code='''import sys
from sticky_intent.cli import main
assert main(['list'])==0
assert not any(n.startswith(('PySide6','tkinter')) for n in sys.modules)
'''
    result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=3)
    assert result.returncode==0,result.stderr
