"""Use the REAL kernel widget lock; cold raise must not need normal CLI machinery."""
import os
import subprocess
import sys
from sticky_intent.instance import WidgetInstance
from sticky_intent.store import Store


def test_raise_works_when_heavy_cli_imports_are_unavailable():
    store = Store()
    owner = WidgetInstance(store.home)
    assert owner.acquire()
    owner.ready()
    code = '''import builtins
from sticky_intent.boot import main
original = builtins.__import__
def light_import(name, *args, **kwargs):
    if name in {'json', 'subprocess', 'uuid', 'tempfile', 'tkinter', 'sticky_intent.store'}:
        raise ImportError('Heavy machinery unavailable during raise: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = light_import
raise SystemExit(main(['widget', '--if-not-running']))
'''
    try:
        result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=3)
        assert result.returncode == 0, result.stderr
        assert owner.poll_raise(), 'The lightweight path must actually request a raise'
        assert not owner.poll_raise()
    finally:
        owner.close()


def test_failed_raise_write_cleans_up_ephemeral_temp(monkeypatch):
    import sticky_intent.wake as wake
    store = Store(); owner = WidgetInstance(store.home); assert owner.acquire()
    def fail(fd, data):
        raise OSError('Injected raise-write failure')
    try:
        import pytest
        with monkeypatch.context() as patch:
            patch.setattr(wake.os, 'write', fail)
            with pytest.raises(OSError, match='raise-write'):
                wake.raise_existing(store.home)
        assert not list(store.home.glob('.widget-raise.*'))
        assert not (store.home / 'widget-raise').exists()
    finally:
        owner.close()


def test_stale_ready_record_does_not_claim_a_live_widget():
    # A dead process can leave readiness metadata. Only the kernel lock decides ownership.
    store = Store()
    (store.home / 'widget-ready.json').write_text('{"pid": 999999, "token": "stale"}')
    env = os.environ.copy(); env.pop('DISPLAY', None); env.pop('WAYLAND_DISPLAY', None)
    result = subprocess.run([sys.executable, '-m', 'sticky_intent', 'widget', '--if-not-running'],
                            capture_output=True, text=True, timeout=3, env=env)
    assert result.returncode != 0 and 'display' in result.stderr.lower()
